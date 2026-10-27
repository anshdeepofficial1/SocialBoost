"""Model training and inference.

Design rules:
* Models are stored per workspace so one account can never score another's data.
* A prediction is only produced from a model trained on that workspace's own
  imported history. Without one, the response is explicitly illustrative.
* Every number is derived from the training data (percentiles, mean engagement,
  feature importances). Nothing is hard-coded to look plausible.
"""

import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.calendar import HistoricalPost
from ..models.model_version import ModelVersion

MODEL_DIR = settings.resolved_model_dir
os.makedirs(MODEL_DIR, exist_ok=True)

BASE_FEATURES = ["duration_seconds", "caption_len", "title_len", "hashtag_count", "hour", "dow"]


def _safe_workspace_key(workspace_id: str | None) -> str:
    return "global" if not workspace_id else "".join(c for c in workspace_id if c.isalnum() or c in "-_")


def artifacts_for(workspace_id: str | None) -> tuple[str, str]:
    key = _safe_workspace_key(workspace_id)
    return (
        os.path.join(MODEL_DIR, f"views_model_{key}.joblib"),
        os.path.join(MODEL_DIR, f"category_model_{key}.joblib"),
    )


def _rows_to_frame(rows: list[HistoricalPost]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "platform": r.platform,
            "published_at": r.published_at,
            "duration_seconds": r.duration_seconds,
            "views": r.views,
            "likes": r.likes,
            "comments": r.comments,
            "shares": r.shares,
            "caption": r.caption,
            "title": r.title,
            "hashtags": r.hashtags,
        }
        for r in rows
    ])


def _build_features(df: pd.DataFrame):
    df = df.copy()
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce").fillna(0).astype(float)
    df["caption_len"] = df["caption"].fillna("").astype(str).str.len()
    df["title_len"] = df["title"].fillna("").astype(str).str.len()
    df["hashtag_count"] = df["hashtags"].fillna("").astype(str).str.count("#")
    published = pd.to_datetime(df["published_at"], errors="coerce")
    df["hour"] = published.dt.hour.fillna(12).astype(int)
    df["dow"] = published.dt.dayofweek.fillna(0).astype(int)
    platform = pd.get_dummies(df["platform"].fillna("instagram"), prefix="plat")
    df = pd.concat([df, platform], axis=1)
    feature_cols = BASE_FEATURES + sorted(c for c in df.columns if c.startswith("plat_"))
    X = df[feature_cols].fillna(0).astype(float)
    return X, feature_cols


def train_models(db: Session, workspace_id: str | None = None):
    q = db.query(HistoricalPost)
    if workspace_id:
        q = q.filter(HistoricalPost.workspace_id == workspace_id)
    rows = q.all()
    if len(rows) < settings.MIN_TRAINING_ROWS:
        return {
            "status": "insufficient_data",
            "n_samples": len(rows),
            "required": settings.MIN_TRAINING_ROWS,
            "message": f"Need at least {settings.MIN_TRAINING_ROWS} historical posts to train. Found {len(rows)}.",
        }

    df = _rows_to_frame(rows)
    X, feature_cols = _build_features(df)
    y_views = pd.to_numeric(df["views"], errors="coerce").fillna(0).astype(float).values

    # Engagement rate per post, used as a second honest target statistic.
    likes = pd.to_numeric(df["likes"], errors="coerce").fillna(0).astype(float).values
    comments = pd.to_numeric(df["comments"], errors="coerce").fillna(0).astype(float).values
    shares = pd.to_numeric(df["shares"], errors="coerce").fillna(0).astype(float).values
    engagements = likes + comments + shares
    with np.errstate(divide="ignore", invalid="ignore"):
        engagement_rates = np.where(y_views > 0, engagements / np.maximum(y_views, 1), 0.0)

    median_views = float(np.median(y_views))
    y_cat = (y_views > median_views).astype(int)

    # With very small datasets a stratified split of the classifier can fail.
    def _split(*arrays):
        try:
            return train_test_split(*arrays, test_size=0.25, random_state=42, stratify=arrays[-1] if len(arrays) > 1 else None)
        except ValueError:
            return train_test_split(*arrays, test_size=0.25, random_state=42)

    Xtr, Xte, ytr, yte = train_test_split(X, y_views, test_size=0.25, random_state=42)
    reg = RandomForestRegressor(n_estimators=150, min_samples_leaf=1, random_state=42)
    reg.fit(Xtr, ytr)
    pred = reg.predict(Xte)
    mae = float(mean_absolute_error(yte, pred)) if len(yte) else 0.0
    r2 = float(r2_score(yte, pred)) if len(yte) > 1 else 0.0

    Xtrc, Xtec, ytrc, ytec = _split(X, y_cat)
    clf = RandomForestClassifier(n_estimators=150, random_state=42)
    clf.fit(Xtrc, ytrc)
    acc = float(accuracy_score(ytec, clf.predict(Xtec))) if len(ytec) else 0.0

    p10, p50, p90 = (float(np.percentile(y_views, p)) for p in (10, 50, 90))
    mean_engagement = float(np.mean(engagement_rates)) if len(engagement_rates) else 0.0
    feature_importance = sorted(
        ({"factor": c, "importance": round(float(v), 4)} for c, v in zip(feature_cols, reg.feature_importances_)),
        key=lambda f: f["importance"],
        reverse=True,
    )

    version = datetime.utcnow().strftime("rf-%Y%m%d%H%M%S")
    views_path, cat_path = artifacts_for(workspace_id)
    artifact = {
        "model": reg,
        "features": feature_cols,
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": len(rows),
        "metrics": {"mae": mae, "r2": r2},
        "views_percentiles": {"p10": p10, "p50": p50, "p90": p90},
        "mean_engagement_rate": mean_engagement,
        "feature_importance": feature_importance,
    }
    joblib.dump(artifact, views_path)
    joblib.dump(
        {"model": clf, "features": feature_cols, "version": version, "n_samples": len(rows), "accuracy": acc, "median_views": median_views},
        cat_path,
    )

    db.add(ModelVersion(
        workspace_id=workspace_id,
        name="views_rf",
        version=version,
        metrics={"mae": mae, "r2": r2, "n_samples": len(rows), "mean_engagement_rate": round(mean_engagement, 4), "p50_views": round(p50, 1)},
        path=views_path,
    ))
    db.add(ModelVersion(
        workspace_id=workspace_id,
        name="category_rf",
        version=version,
        metrics={"accuracy": acc, "n_samples": len(rows), "median_views": round(median_views, 1)},
        path=cat_path,
    ))
    db.commit()

    return {
        "status": "trained",
        "version": version,
        "n_samples": len(rows),
        "metrics": {"mae": mae, "r2": r2, "accuracy": acc},
        "views_percentiles": {"p10": p10, "p50": p50, "p90": p90},
        "top_features": feature_importance[:4],
    }


def _confidence_from(r2: float, n_samples: int, accuracy: float) -> float:
    """Confidence rises with fit quality and data volume, and stays humble."""
    fit = max(0.0, min(1.0, (r2 + 1) / 2))  # r2 of -1..1 mapped to 0..1
    volume = min(1.0, n_samples / 60.0)
    raw = 0.25 + 0.4 * fit + 0.2 * volume + 0.15 * accuracy
    return round(max(0.05, min(0.9, raw)), 2)


def model_status(workspace_id: str | None) -> dict:
    views_path, cat_path = artifacts_for(workspace_id)
    if not (os.path.exists(views_path) and os.path.exists(cat_path)):
        return {"available": False}
    art = joblib.load(views_path)
    return {
        "available": True,
        "version": art.get("version"),
        "trained_at": art.get("trained_at"),
        "n_samples": art.get("n_samples"),
        "metrics": art.get("metrics", {}),
        "views_percentiles": art.get("views_percentiles", {}),
        "top_features": art.get("feature_importance", [])[:4],
    }


def _illustrative(video_features: dict, platform: str, reason: str) -> dict:
    return {
        "performance_score": None,
        "expected_views_low": None,
        "expected_views_high": None,
        "expected_engagement_rate": None,
        "category": "unknown",
        "confidence": 0.0,
        "factors": [],
        "model_version": "none",
        "note": reason,
    }


def predict(video_features: dict, platform: str, db: Session, workspace_id: str | None = None) -> dict:
    views_path, cat_path = artifacts_for(workspace_id)
    if not (os.path.exists(views_path) and os.path.exists(cat_path)):
        return _illustrative(
            video_features,
            platform,
            "No model has been trained on this workspace's history yet. "
            f"Import at least {settings.MIN_TRAINING_ROWS} historical posts and train before trusting a number.",
        )

    reg_art = joblib.load(views_path)
    cat_art = joblib.load(cat_path)
    reg = reg_art["model"]
    clf = cat_art["model"]
    features = reg_art["features"]

    dur = float(video_features.get("duration_seconds") or 0)
    caption = video_features.get("caption") or ""
    title = video_features.get("title") or ""
    hashtags = video_features.get("hashtags") or ""
    published = video_features.get("published_at")
    try:
        when = pd.to_datetime(published) if published else pd.Timestamp.utcnow()
    except Exception:
        when = pd.Timestamp.utcnow()

    row = {
        "duration_seconds": dur,
        "caption_len": len(caption),
        "title_len": len(title),
        "hashtag_count": hashtags.count("#"),
        "hour": int(when.hour),
        "dow": int(when.dayofweek),
    }
    for f in features:
        if f.startswith("plat_"):
            row[f] = 1 if f == f"plat_{platform}" else 0

    X = pd.DataFrame([row])[features].fillna(0).astype(float)
    views = float(reg.predict(X)[0])
    cat = int(clf.predict(X)[0])

    percentiles = reg_art.get("views_percentiles", {})
    p10, p50, p90 = percentiles.get("p10"), percentiles.get("p50"), percentiles.get("p90")

    # Score = where the predicted views sit in the workspace's own distribution.
    if p10 is not None and p90 is not None and p90 > p10:
        score = int(max(0, min(100, round((views - p10) / (p90 - p10) * 100))))
    else:
        score = 50

    if p10 is not None and p50:
        category = "above_typical" if views > p50 else "below_typical"
    else:
        category = "above_typical" if cat == 1 else "below_typical"

    importances = {f["factor"]: f["importance"] for f in reg_art.get("feature_importance", [])}
    factors = [
        {"factor": f, "value": float(X[f].iloc[0]), "importance": float(importances.get(f, 0.0))}
        for f in features
    ]
    factors.sort(key=lambda f: f["importance"], reverse=True)

    metrics = reg_art.get("metrics", {})
    r2 = float(metrics.get("r2", 0.0))
    acc = float(cat_art.get("accuracy", 0.0))
    confidence = _confidence_from(r2, int(reg_art.get("n_samples", 0)), acc)

    mean_engagement = reg_art.get("mean_engagement_rate")
    spread = 0.25
    return {
        "performance_score": score,
        "expected_views_low": int(max(0, views * (1 - spread))),
        "expected_views_high": int(views * (1 + spread)),
        "expected_engagement_rate": float(mean_engagement) if mean_engagement is not None else None,
        "category": category,
        "confidence": confidence,
        "factors": factors,
        "model_version": reg_art.get("version", "unknown"),
        "percentiles": percentiles,
        "metrics": {"mae": metrics.get("mae"), "r2": metrics.get("r2"), "samples": reg_art.get("n_samples"), "accuracy": acc},
        "note": (
            "Estimate from a model trained on this workspace's imported history. "
            "The range is the point estimate ±25% and is not a guarantee of performance."
        ),
    }
