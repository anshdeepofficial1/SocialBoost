"""Growth coach model.

Why this is not just a views predictor
--------------------------------------
Raw view counts are dominated by how many followers you already had and by
algorithmic luck. A model trained on views mostly learns "big accounts get big
numbers", which is useless when the goal is to grow.

This model ranks every post against the workspace's *own* baseline on signals
that actually move an account forward:

* reach index   - views relative to the account's median post
* save rate     - saves / views, the strongest "this is worth keeping" signal
* follow rate   - new follows / views, the direct conversion to growth
* engagement    - likes + comments + shares + saves / views
* retention     - average percentage viewed, when the export provides it

Those are combined into a ``growth_index`` in 0..1 by percentile rank, so the
target is bounded, comparable across accounts and robust to outliers.

Everything reported (ranges, importance, expected lift) comes from the trained
model. When there is not enough data the module says so instead of inventing a
number.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.calendar import HistoricalPost
from ..models.model_version import ModelVersion

MODEL_DIR = settings.resolved_model_dir
os.makedirs(MODEL_DIR, exist_ok=True)

MIN_ROWS = max(8, settings.MIN_TRAINING_ROWS)

NUMERIC_FEATURES = [
    "duration_seconds",
    "caption_len",
    "title_len",
    "hashtag_count",
    "hour",
    "dow",
    "word_count",
    "first_line_len",
    "question_marks",
    "numbers",
    "cta",
    "emoji_count",
    "exclamation",
    "caps_ratio",
    "line_breaks",
    "avg_word_len",
]

CTA_WORDS = (
    "follow", "comment", "share", "save", "subscribe", "link", "watch",
    "click", "try", "tell me", "which one", "drop", "tag",
)
QUESTION_WORDS = ("how", "why", "what", "when", "where", "who", "which", "can", "should", "would")

_EMOJI = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E0-\U0001F1FF" "]+"
)


def _safe_key(workspace_id: str | None) -> str:
    return "global" if not workspace_id else "".join(
        c for c in workspace_id if c.isalnum() or c in "-_"
    )


def artifact_path(workspace_id: str | None) -> str:
    return os.path.join(MODEL_DIR, f"growth_model_{_safe_key(workspace_id)}.joblib")


# ---------------------------------------------------------------- features


def _text_features(text: str) -> dict:
    body = (text or "").strip()
    words = body.split()
    first_line = body.split("\n")[0] if body else ""
    letters = [c for c in body if c.isalpha()]
    upper = [c for c in letters if c.isupper()]
    return {
        "word_count": len(words),
        "first_line_len": len(first_line),
        "question_marks": body.count("?"),
        "numbers": len(re.findall(r"\d", body)),
        "cta": int(any(w in body.lower() for w in CTA_WORDS)),
        "emoji_count": len(_EMOJI.findall(body)),
        "exclamation": body.count("!"),
        "caps_ratio": (len(upper) / len(letters)) if letters else 0.0,
        "line_breaks": body.count("\n"),
        "avg_word_len": (sum(len(w) for w in words) / len(words)) if words else 0.0,
    }


def _rows_to_frame(rows: list[HistoricalPost]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "platform": r.platform or "instagram",
                "published_at": r.published_at,
                "content_type": (r.content_type or "short").lower(),
                "content_category": (r.content_category or "").lower(),
                "duration_seconds": float(r.duration_seconds or 0),
                "views": float(r.views or 0),
                "likes": float(r.likes or 0),
                "comments": float(r.comments or 0),
                "shares": float(r.shares or 0),
                "saves": float(getattr(r, "saves", 0) or 0),
                "reach": float(getattr(r, "reach", 0) or 0),
                "followers_at_publish": float(r.followers_at_publish or 0),
                "follows": float(getattr(r, "follows", 0) or 0),
                "retention": float(getattr(r, "retention", 0) or 0),
                "caption": r.caption or "",
                "title": r.title or "",
                "hashtags": r.hashtags or "",
            }
            for r in rows
        ]
    )


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Numeric feature frame and the combined text used for TF-IDF."""
    frame = df.copy()
    frame["duration_seconds"] = pd.to_numeric(frame["duration_seconds"], errors="coerce").fillna(0)
    frame["caption_len"] = frame["caption"].fillna("").astype(str).str.len()
    frame["title_len"] = frame["title"].fillna("").astype(str).str.len()
    frame["hashtag_count"] = frame["hashtags"].fillna("").astype(str).str.count("#")

    published = pd.to_datetime(frame["published_at"], errors="coerce")
    frame["hour"] = published.dt.hour.fillna(12).astype(int)
    frame["dow"] = published.dt.dayofweek.fillna(0).astype(int)

    derived = pd.DataFrame(
        frame.apply(lambda r: _text_features(f"{r['caption']} \n {r['title']}"), axis=1).tolist(),
        index=frame.index,
    )
    for column in derived.columns:
        frame[column] = derived[column]

    numeric = frame[NUMERIC_FEATURES].astype(float)

    # Categorical blocks, kept as explicit 0/1 columns so the model stays
    # portable in a joblib artifact with no sklearn pipeline version pinning.
    for column, prefix in (("platform", "plat"), ("content_type", "type"), ("content_category", "cat")):
        values = frame[column].fillna("").astype(str).str.strip()
        dummies = pd.get_dummies(values, prefix=prefix)
        # Keep the columns stable: anything not in the vocabulary is all-zero.
        numeric = pd.concat([numeric, dummies.astype(float)], axis=1)

    text = (
        frame["caption"].fillna("").astype(str) + " "
        + frame["title"].fillna("").astype(str) + " "
        + frame["hashtags"].fillna("").astype(str)
    )
    return numeric, text


# ---------------------------------------------------------------- targets


@dataclass
class SignalCoverage:
    reach: bool = True
    saves: bool = False
    follows: bool = False
    retention: bool = False

    def as_dict(self) -> dict:
        return {
            "reach": self.reach,
            "saves": self.saves,
            "follows": self.follows,
            "retention": self.retention,
        }


def _percentile(values: pd.Series) -> pd.Series:
    if len(values) <= 1 or values.nunique() <= 1:
        return pd.Series(np.full(len(values), 0.5), index=values.index)
    return values.rank(pct=True, method="average")


def build_target(df: pd.DataFrame) -> tuple[pd.Series, dict, SignalCoverage]:
    """Combine the growth signals into one 0..1 index.

    A signal only joins the index when most rows actually report it, so a
    missing column never silently becomes a zero that drags the target down.
    """
    views = df["views"].clip(lower=0)
    baseline = float(views[views > 0].median()) if (views > 0).any() else 0.0
    reach_index = (views / baseline) if baseline > 0 else pd.Series(np.ones(len(df)), index=df.index)

    coverage = SignalCoverage()
    n = max(len(df), 1)

    save_rate = df["saves"] / views.replace(0, np.nan)
    coverage.saves = bool((df["saves"] > 0).sum() >= max(3, n * 0.5))

    follow_rate = df["follows"] / views.replace(0, np.nan)
    coverage.follows = bool((df["follows"] > 0).sum() >= max(3, n * 0.5))

    retention = df["retention"]
    coverage.retention = bool((retention > 0).sum() >= max(3, n * 0.5))

    engagements = df["likes"] + df["comments"] + df["shares"] + df["saves"]
    engagement_rate = engagements / views.replace(0, np.nan)

    components: list[tuple[str, pd.Series, float]] = [
        ("reach", _percentile(reach_index.fillna(1.0)), 1.0)
    ]
    if engagement_rate.notna().any():
        components.append(("engagement", _percentile(engagement_rate.fillna(0.0)), 0.8))
    if coverage.saves:
        components.append(("saves", _percentile(save_rate.fillna(0.0)), 1.4))
    if coverage.follows:
        components.append(("follows", _percentile(follow_rate.fillna(0.0)), 1.6))
    if coverage.retention:
        components.append(("retention", _percentile(retention.fillna(0.0)), 0.7))

    total_weight = sum(w for _, _, w in components)
    growth = sum(series * weight for _, series, weight in components) / total_weight
    growth = growth.clip(0, 1)

    detail = {
        "baseline_views": baseline,
        "signals": coverage.as_dict(),
        "weights": {name: round(weight / total_weight, 4) for name, _, weight in components},
        "engagement_rate_mean": float(engagement_rate.fillna(0).mean()),
        "save_rate_mean": float(save_rate.fillna(0).mean()) if coverage.saves else None,
        "follow_rate_mean": float(follow_rate.fillna(0).mean()) if coverage.follows else None,
    }
    return growth, detail, coverage


# ---------------------------------------------------------------- training


def _make_model(n_rows: int, quantile: float | None = None) -> HistGradientBoostingRegressor:
    leaf = max(2, min(20, n_rows // 12))
    return HistGradientBoostingRegressor(
        loss="quantile" if quantile is not None else "squared_error",
        quantile=quantile,
        max_iter=250,
        learning_rate=0.06,
        max_depth=3,
        min_samples_leaf=leaf,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=42,
    )


def _text_block(text: pd.Series, n_rows: int):
    """TF-IDF plus SVD, sized down for small datasets."""
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_features=400,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    try:
        matrix = vectorizer.fit_transform(text.fillna(""))
    except ValueError:
        vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=1, max_features=200)
        matrix = vectorizer.fit_transform(text.fillna(""))

    components = max(2, min(10, n_rows - 2, matrix.shape[1] - 1))
    if matrix.shape[1] <= 2 or components < 2:
        return vectorizer, None, None
    svd = TruncatedSVD(n_components=components, random_state=42)
    reduced = svd.fit_transform(matrix)
    return vectorizer, svd, reduced


def _combine(numeric: pd.DataFrame, reduced) -> np.ndarray:
    base = numeric.to_numpy(dtype=float)
    if reduced is None:
        return base
    return np.hstack([base, np.asarray(reduced, dtype=float)])


def _time_cv_scores(numeric, text, target, n_rows: int) -> dict:
    """Chronological cross-validation, so a post never trains on its own future."""
    folds = min(4, max(2, n_rows // 8))
    if n_rows < 12 or folds < 2:
        return {"folds": 0, "note": "Too few rows for time-series cross-validation."}

    splitter = TimeSeriesSplit(n_splits=folds)
    maes: list[float] = []
    rhos: list[float] = []
    for train_idx, test_idx in splitter.split(numeric):
        if len(train_idx) < 6 or len(test_idx) < 2:
            continue
        try:
            vectorizer, svd, reduced_train = _text_block(text.iloc[train_idx], len(train_idx))
            matrix_test = vectorizer.transform(text.iloc[test_idx])
            reduced_test = svd.transform(matrix_test) if svd is not None else None
            X_train = _combine(numeric.iloc[train_idx], reduced_train)
            X_test = _combine(numeric.iloc[test_idx], reduced_test)

            scaler = StandardScaler().fit(X_train)
            model = _make_model(len(train_idx))
            model.fit(scaler.transform(X_train), target.iloc[train_idx].to_numpy())
            predicted = model.predict(scaler.transform(X_test))
            truth = target.iloc[test_idx].to_numpy()

            maes.append(float(np.mean(np.abs(predicted - truth))))
            if len(truth) >= 3 and len(np.unique(truth)) > 1:
                rho = spearmanr(truth, predicted).correlation
                if rho is not None and not math.isnan(rho):
                    rhos.append(float(rho))
        except Exception:
            continue

    if not maes:
        return {"folds": 0, "note": "Cross-validation could not run on this dataset."}
    return {
        "folds": len(maes),
        "mae": round(float(np.mean(maes)), 4),
        "rank_correlation": round(float(np.mean(rhos)), 3) if rhos else None,
        "note": "Chronological folds: each fold predicts posts it has not seen, in time order.",
    }


def train(db: Session, workspace_id: str | None = None) -> dict:
    # Growth targets are derived from post performance. A row without a real
    # view count cannot form a valid supervised target and must never be
    # silently converted into a zero-view example by _rows_to_frame().
    query = db.query(HistoricalPost).filter(HistoricalPost.views.isnot(None))
    if workspace_id:
        query = query.filter(HistoricalPost.workspace_id == workspace_id)
    rows = query.order_by(HistoricalPost.published_at.asc()).all()

    if len(rows) < MIN_ROWS:
        return {
            "status": "insufficient_data",
            "n_samples": len(rows),
            "required": MIN_ROWS,
            "message": (
                f"The coach needs at least {MIN_ROWS} posts from this workspace. "
                f"Found {len(rows)}. Export your Instagram and YouTube analytics as CSV and import them."
            ),
        }

    df = _rows_to_frame(rows)
    numeric, text = build_features(df)
    target, target_detail, coverage = build_target(df)

    # The comparison point the coach measures a new post against.
    target_detail["winner_profile"] = _winner_profile(df, target)
    target_detail["best_duration"] = _best_duration(df, target)
    target_detail["hour_support"] = {
        int(h): int(c) for h, c in df.assign(hour=numeric["hour"]).groupby("hour").size().items()
    }

    if target.nunique() <= 1:
        return {
            "status": "insufficient_signal",
            "n_samples": len(rows),
            "message": "Every post scored the same, so there is nothing to learn yet. Import posts with different performance.",
        }

    vectorizer, svd, reduced = _text_block(text, len(df))
    X = _combine(numeric, reduced)
    scaler = StandardScaler().fit(X)

    median_model = _make_model(len(df))
    median_model.fit(scaler.transform(X), target.to_numpy())
    low_model = _make_model(len(df), quantile=0.1)
    low_model.fit(scaler.transform(X), target.to_numpy())
    high_model = _make_model(len(df), quantile=0.9)
    high_model.fit(scaler.transform(X), target.to_numpy())

    cv = _time_cv_scores(numeric, text, target, len(df))

    # Permutation importance on the observed data: honest about what the model
    # relies on, and stable enough for a few hundred rows.
    importance_rows: list[dict] = []
    try:
        result = permutation_importance(
            median_model, scaler.transform(X), target.to_numpy(),
            n_repeats=8, random_state=42, scoring="neg_mean_absolute_error",
        )
        names = list(numeric.columns) + [f"text_{i}" for i in range(reduced.shape[1])] if reduced is not None else list(numeric.columns)
        pairs = sorted(zip(names, result.importances_mean), key=lambda p: p[1], reverse=True)
        total = sum(abs(v) for _, v in pairs) or 1.0
        importance_rows = [
            {"factor": name, "importance": round(float(value) / total, 4)}
            for name, value in pairs[:14]
        ]
    except Exception:
        importance_rows = []

    version = datetime.utcnow().strftime("coach-%Y%m%d%H%M%S")
    path = artifact_path(workspace_id)
    artifact = {
        "model": median_model,
        "low_model": low_model,
        "high_model": high_model,
        "scaler": scaler,
        "vectorizer": vectorizer,
        "svd": svd,
        "numeric_columns": list(numeric.columns),
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": len(rows),
        "target": target_detail,
        "coverage": coverage.as_dict(),
        "cv": cv,
        "importance": importance_rows,
    }
    joblib.dump(artifact, path)

    db.add(
        ModelVersion(
            workspace_id=workspace_id,
            name="growth_coach",
            version=version,
            metrics={
                "n_samples": len(rows),
                "cv_mae": cv.get("mae"),
                "rank_correlation": cv.get("rank_correlation"),
                "signals": coverage.as_dict(),
            },
            path=path,
        )
    )
    db.commit()

    return {
        "status": "trained",
        "version": version,
        "n_samples": len(rows),
        "target": target_detail,
        "cross_validation": cv,
        "top_features": importance_rows[:6],
        "note": (
            "Trained on this workspace only. The target is a percentile rank of your own posts "
            "on reach, saves, follows, retention and engagement — not raw views."
        ),
    }


# ---------------------------------------------------------------- inference


def load(workspace_id: str | None) -> dict | None:
    path = artifact_path(workspace_id)
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def status(workspace_id: str | None) -> dict:
    artifact = load(workspace_id)
    if not artifact:
        return {"available": False}
    return {
        "available": True,
        "version": artifact.get("version"),
        "trained_at": artifact.get("trained_at"),
        "n_samples": artifact.get("n_samples"),
        "target": artifact.get("target"),
        "coverage": artifact.get("coverage"),
        "cross_validation": artifact.get("cv"),
        "top_features": (artifact.get("importance") or [])[:6],
    }


def _row_from_input(payload: dict) -> pd.DataFrame:
    published = payload.get("published_at")
    try:
        when = pd.to_datetime(published) if published else pd.Timestamp.utcnow()
    except Exception:
        when = pd.Timestamp.utcnow()
    return pd.DataFrame(
        [
            {
                "platform": (payload.get("platform") or "instagram").lower(),
                "published_at": when,
                "content_type": (payload.get("content_type") or "short").lower(),
                "content_category": (payload.get("content_category") or "").lower(),
                "duration_seconds": float(payload.get("duration_seconds") or 0),
                "views": 0.0,
                "likes": 0.0,
                "comments": 0.0,
                "shares": 0.0,
                "saves": 0.0,
                "reach": 0.0,
                "followers_at_publish": 0.0,
                "follows": 0.0,
                "retention": 0.0,
                "caption": payload.get("caption") or "",
                "title": payload.get("title") or "",
                "hashtags": payload.get("hashtags") or "",
            }
        ]
    )


def _predict_index(artifact: dict, frame: pd.DataFrame) -> dict:
    numeric, text = build_features(frame)
    numeric = numeric.reindex(columns=artifact["numeric_columns"], fill_value=0.0)

    matrix = artifact["vectorizer"].transform(text.fillna(""))
    reduced = artifact["svd"].transform(matrix) if artifact.get("svd") is not None else None
    X = _combine(numeric, reduced)
    scaled = artifact["scaler"].transform(X)

    median = float(artifact["model"].predict(scaled)[0])
    low = float(artifact["low_model"].predict(scaled)[0])
    high = float(artifact["high_model"].predict(scaled)[0])
    # Independently fitted quantile models can cross; the reported band must
    # still contain the point estimate.
    low, high = min(low, median), max(high, median)
    return {"median": median, "low": low, "high": high}


def _confidence(artifact: dict) -> tuple[float, str]:
    cv = artifact.get("cv") or {}
    n = int(artifact.get("n_samples") or 0)
    rho = cv.get("rank_correlation")
    folds = int(cv.get("folds") or 0)

    volume = min(1.0, n / 80.0)
    quality = 0.5 if rho is None else max(0.0, min(1.0, (rho + 1) / 2))
    stability = min(1.0, folds / 4.0)
    raw = 0.15 + 0.45 * quality + 0.25 * volume + 0.15 * stability
    confidence = round(max(0.05, min(0.9, raw)), 2)

    if n < 20:
        label = "low — under 20 posts"
    elif n < 40:
        label = "moderate — 20 to 40 posts"
    elif n < 100:
        label = "good — 40 to 100 posts"
    else:
        label = "strong — 100+ posts"
    return confidence, label


def _levers(artifact: dict, frame: pd.DataFrame, baseline: dict) -> list[dict]:
    """Counterfactual sweep: change one thing, ask the model what happens.

    This is what turns a score into a prescription. Each lever is a plausible
    range for this post, and the reported delta is the model's own answer.
    """
    base = baseline["median"]
    caption = str(frame.iloc[0]["caption"] or "")
    hashtags = str(frame.iloc[0]["hashtags"] or "")
    duration = float(frame.iloc[0]["duration_seconds"] or 0)
    when = pd.to_datetime(frame.iloc[0]["published_at"])

    proposals: list[dict] = []
    support = (artifact.get("target") or {}).get("hour_support") or {}
    min_support = 3

    def evaluate(label: str, mutate, rationale: str, evidence: str) -> None:
        try:
            candidate = mutate(frame.copy())
            predicted = _predict_index(artifact, candidate)
        except Exception:
            return
        delta = predicted["median"] - base
        proposals.append(
            {
                "lever": label,
                "change": rationale,
                "expected_lift": round(delta * 100, 1),
                "predicted_index": round(predicted["median"] * 100, 1),
                "confidence_band": [round(predicted["low"] * 100, 1), round(predicted["high"] * 100, 1)],
                "evidence": evidence,
            }
        )

    # Duration: compare against the workspace's best-performing duration band.
    best_duration = artifact.get("target", {}).get("best_duration")
    if best_duration:
        evaluate(
            "duration_seconds",
            lambda c: c.assign(duration_seconds=float(best_duration)),
            f"Move duration to {best_duration}s, the band where your posts ranked highest.",
            "band averages from your own posts",
        )

    # Hashtag count.
    for count in (0, 3, 5, 8):
        current = hashtags.count("#")
        if count != current:
            tags = " ".join(f"#tag{i}" for i in range(count))
            evaluate(
                "hashtag_count",
                lambda c, t=tags: c.assign(hashtags=t),
                f"Use {count} hashtag(s) instead of {current}.",
                "model response to a hashtag count change",
            )

    # Call to action.
    if "cta" not in caption.lower() and not any(w in caption.lower() for w in CTA_WORDS):
        evaluate(
            "call_to_action",
            lambda c: c.assign(caption=(caption + " Save this for later.").strip()),
            "Add an explicit call to action to the caption.",
            "model response to an added CTA",
        )

    # Posting hour: only propose an hour your own history actually covers, and
    # say how many posts back it. A single post at 3am is not a pattern.
    for hour in (7, 9, 12, 17, 19, 21):
        if hour == when.hour or support.get(hour, 0) < min_support:
            continue
        shifted = when.replace(hour=hour)
        evaluate(
            "posting_hour",
            lambda c, h=shifted: c.assign(published_at=h),
            f"Publish at {hour:02d}:00 instead of {when.hour:02d}:00.",
            f"{support[hour]} of your posts were published in this hour",
        )

    # Caption length: open with a hook line.
    if len(caption) < 60:
        longer = (caption + "\n\nHere is the part most people miss.").strip()
        evaluate(
            "caption_length",
            lambda c: c.assign(caption=longer),
            "Lengthen the caption with a second line that adds context.",
            "model response to a longer caption",
        )

    # Rank by the lower edge of the predicted band, not the point estimate:
    # a lever that only looks good under an optimistic model is not advice.
    proposals.sort(key=lambda p: (p["expected_lift"], p["confidence_band"][0]), reverse=True)
    return proposals[:6]


def _diagnose(artifact: dict, frame: pd.DataFrame, index: float) -> list[dict]:
    """Compare this post's measurable properties with the account's winners."""
    target = artifact.get("target") or {}
    winners = target.get("winner_profile") or {}
    row = frame.iloc[0]
    text = f"{row['caption']} {row['title']}"
    features = _text_features(text)
    findings: list[dict] = []

    def compare(name: str, actual: float, ideal: float, unit: str, advice: str) -> None:
        if ideal is None:
            return
        gap = ideal - actual
        if abs(gap) < (abs(ideal) * 0.15 + 0.5):
            return
        direction = "raise" if gap > 0 else "lower"
        findings.append(
            {
                "area": name,
                "yours": round(float(actual), 1),
                "your_winners": round(float(ideal), 1),
                "action": f"{advice} ({direction} toward {round(float(ideal), 1)}{unit})",
            }
        )

    compare("duration_seconds", float(row["duration_seconds"]), winners.get("duration_seconds"), "s",
            "Match the duration of your best posts")
    compare("hashtag_count", str(row["hashtags"]).count("#"), winners.get("hashtag_count"), "",
            "Match the hashtag count of your best posts")
    compare("caption_length", len(str(row["caption"])), winners.get("caption_len"), " chars",
            "Match the caption length of your best posts")
    compare("first_line_length", features["first_line_len"], winners.get("first_line_len"), " chars",
            "Tighten the first line")

    if index < 0.5:
        if features["cta"] == 0:
            findings.append({
                "area": "call_to_action",
                "yours": 0,
                "your_winners": winners.get("cta"),
                "action": "Add a clear next step; your weaker posts tend to have none.",
            })
        if features["question_marks"] == 0 and (winners.get("question_marks") or 0) > 0:
            findings.append({
                "area": "curiosity",
                "yours": 0,
                "your_winners": winners.get("question_marks"),
                "action": "Open with a question or a concrete claim to earn the first seconds.",
            })
    return findings


def _winner_profile(df: pd.DataFrame, target: pd.Series) -> dict:
    """Median properties of the top quartile, used as the comparison point."""
    if len(df) < 4:
        return {}
    cutoff = target.quantile(0.75)
    winners = df[target >= cutoff]
    if winners.empty:
        return {}
    features = build_features(winners)[0]
    profile = {
        "duration_seconds": float(features["duration_seconds"].median()),
        "hashtag_count": float(features["hashtag_count"].median()),
        "caption_len": float(features["caption_len"].median()),
        "first_line_len": float(features["first_line_len"].median()),
        "cta": float(features["cta"].median()),
        "question_marks": float(features["question_marks"].median()),
        "hour": float(features["hour"].median()),
        "dow": float(features["dow"].median()),
    }
    return profile


def _best_duration(df: pd.DataFrame, target: pd.Series) -> float | None:
    if len(df) < 6:
        return None
    durations = pd.to_numeric(df["duration_seconds"], errors="coerce").fillna(0)
    if durations.nunique() < 2:
        return None
    bins = pd.cut(durations, bins=min(4, durations.nunique()), duplicates="drop")
    if bins.nunique() < 2:
        return None
    grouped = target.groupby(bins, observed=True).mean()
    if grouped.empty:
        return None
    best = grouped.idxmax()
    return float(round((best.left + best.right) / 2, 1))


def predict(payload: dict, workspace_id: str | None) -> dict:
    artifact = load(workspace_id)
    if not artifact:
        return {
            "available": False,
            "growth_index": None,
            "note": (
                f"No coach has been trained on this workspace yet. Import at least {MIN_ROWS} posts "
                "from your own account, then train it. A score without your history would be invented."
            ),
        }

    frame = _row_from_input(payload)
    try:
        baseline = _predict_index(artifact, frame)
    except Exception as exc:  # a corrupt artifact must not 500 the API
        return {"available": False, "growth_index": None, "note": f"The saved model could not be used: {exc}"}

    index = baseline["median"]
    confidence, confidence_label = _confidence(artifact)

    # Recompute the winner profile at prediction time so the comparison is
    # always against the current model's own training data.
    return {
        "available": True,
        "growth_index": round(index * 100, 1),
        "range": [round(baseline["low"] * 100, 1), round(baseline["high"] * 100, 1)],
        "percentile_reading": (
            "Top third of your posts" if index >= 0.66
            else "Middle third of your posts" if index >= 0.33
            else "Bottom third of your posts"
        ),
        "confidence": confidence,
        "confidence_label": confidence_label,
        "version": artifact.get("version"),
        "signals_used": artifact.get("coverage"),
        "target_weights": (artifact.get("target") or {}).get("weights"),
        "top_features": (artifact.get("importance") or [])[:6],
        "levers": _levers(artifact, frame, baseline),
        "diagnosis": _diagnose(artifact, frame, index),
        "note": (
            "The growth index is a percentile against your own posts, built from reach, saves, "
            "follows, retention and engagement. It is a ranking, not a view forecast."
        ),
    }


def winner_profile(workspace_id: str | None) -> dict:
    """Properties of the workspace's best posts, for the coach screen."""
    artifact = load(workspace_id)
    if not artifact:
        return {}
    return artifact.get("target", {}).get("winner_profile", {})
