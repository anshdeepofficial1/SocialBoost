from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..db.session import get_db
from .deps import get_current_user, get_workspace_id
from ..models.video import Video
from ..models.calendar import HistoricalPost
from ..models.prediction import Prediction
from ..services.ml_service import predict, train_models, model_status

router = APIRouter(prefix="/predictions", tags=["predictions"])

PLATFORMS = {"instagram", "youtube"}


class PredictIn(BaseModel):
    video_id: str | None = None
    platform: str = "instagram"
    caption: str = ""
    title: str = ""
    hashtags: str = ""
    duration_seconds: float = Field(default=0.0, ge=0, le=3600)


@router.post("/run")
def run_prediction(payload: PredictIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")

    video_id = payload.video_id or None
    duration = payload.duration_seconds

    if video_id:
        video = (
            db.query(Video)
            .filter(Video.id == video_id, Video.workspace_id == ws_id)
            .first()
        )
        if not video:
            raise HTTPException(404, "Video not found in this workspace")
        if not duration:
            duration = float(video.duration_seconds or 0)

    features = {
        "duration_seconds": duration,
        "caption": payload.caption,
        "title": payload.title,
        "hashtags": payload.hashtags,
    }
    res = predict(features, platform, db, ws_id)

    pred = Prediction(
        workspace_id=ws_id,
        video_id=video_id,
        platform=platform,
        performance_score=res["performance_score"],
        expected_views_low=res["expected_views_low"],
        expected_views_high=res["expected_views_high"],
        expected_engagement_rate=res["expected_engagement_rate"],
        category=res["category"],
        confidence=res["confidence"],
        factors=res["factors"],
        model_version=res["model_version"],
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return {"prediction_id": pred.id, **res}


@router.post("/train")
def train(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return train_models(db, ws_id)


@router.get("/status")
def status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models.model_version import ModelVersion

    ws_id = get_workspace_id(user, db)
    versions = (
        db.query(ModelVersion)
        .filter(ModelVersion.workspace_id == ws_id)
        .order_by(ModelVersion.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {"name": v.name, "version": v.version, "metrics": v.metrics, "created_at": v.created_at}
        for v in versions
    ]


@router.get("/model")
def model(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    status = model_status(ws_id)
    if status.get("available"):
        return status

    # Render's ephemeral filesystem can discard sklearn artifacts between
    # restarts while the durable database still has the synced training rows.
    # Rebuild from this workspace's actual posts rather than showing a stale
    # "no model" state or fabricating a prediction.
    usable_rows = (
        db.query(HistoricalPost)
        .filter(
            HistoricalPost.workspace_id == ws_id,
            HistoricalPost.views.isnot(None),
        )
        .count()
    )
    from ..core.config import settings
    if usable_rows >= settings.MIN_TRAINING_ROWS:
        trained = train_models(db, ws_id)
        if trained.get("status") == "trained":
            return model_status(ws_id)
    return status


@router.get("")
def history(limit: int = 50, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    rows = (
        db.query(Prediction)
        .filter(Prediction.workspace_id == ws_id)
        .order_by(Prediction.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": p.id,
            "video_id": p.video_id,
            "platform": p.platform,
            "performance_score": p.performance_score,
            "expected_views_low": p.expected_views_low,
            "expected_views_high": p.expected_views_high,
            "expected_engagement_rate": p.expected_engagement_rate,
            "category": p.category,
            "confidence": p.confidence,
            "model_version": p.model_version,
            "created_at": p.created_at,
        }
        for p in rows
    ]
