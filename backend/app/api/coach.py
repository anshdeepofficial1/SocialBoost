"""Growth coach and voice writer endpoints.

These are additive to the existing prediction endpoints. The old model still
works; this is the part that answers "what should I change to grow".
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..services import growth_model, voice_model
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/coach", tags=["coach"])

PLATFORMS = {"instagram", "youtube"}


class CoachIn(BaseModel):
    platform: str = "instagram"
    caption: str = ""
    title: str = ""
    hashtags: str = ""
    content_type: str = "short"
    content_category: str = ""
    duration_seconds: float = Field(default=0.0, ge=0, le=3600)
    published_at: str | None = None


class WriteIn(BaseModel):
    topic: str = ""
    platform: str = "instagram"
    kind: str = "caption"
    count: int = Field(default=3, ge=1, le=6)
    temperature: float = Field(default=0.8, ge=0.2, le=1.5)


class HookIn(BaseModel):
    topic: str = ""
    count: int = Field(default=5, ge=1, le=10)


@router.post("/train")
def train_coach(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return growth_model.train(db, ws_id)


@router.get("/status")
def coach_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    current = growth_model.status(ws_id)
    available_rows = (
        db.query(HistoricalPost)
        .filter(
            HistoricalPost.workspace_id == ws_id,
            HistoricalPost.views.isnot(None),
        )
        .count()
    )
    # Render can discard local model artifacts while the database survives.
    # Rebuild the workspace's coach model from its own real-view history.
    needs_rebuild = (
        not current.get("available")
        or not str(current.get("version") or "").startswith("coach-v2-")
    )
    if needs_rebuild and available_rows >= growth_model.MIN_ROWS:
        try:
            growth_model.train(db, ws_id)
        except Exception:
            import logging
            logging.getLogger("socialboost.ml").exception(
                "automatic growth-coach rebuild failed for workspace %s", ws_id
            )
        current = growth_model.status(ws_id)
    current["n_samples_available"] = available_rows
    current["required"] = growth_model.MIN_ROWS
    if not current.get("available") and "note" not in current:
        current["note"] = (
            f"Growth Coach requires at least {growth_model.MIN_ROWS} posts with real view counts. "
            f"Found {available_rows}; sync the connected accounts to build its dataset."
        )
    return current


@router.post("/score")
def score(payload: CoachIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    data = payload.model_dump()
    data["platform"] = platform
    return growth_model.predict(data, ws_id)


@router.get("/winners")
def winners(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The profile of your best posts, with the evidence behind each number."""
    ws_id = get_workspace_id(user, db)
    profile = growth_model.winner_profile(ws_id)
    artifact = growth_model.load(ws_id)
    if not artifact:
        return {"available": False, "profile": {}, "note": "Train the coach first."}

    rows = (
        db.query(HistoricalPost)
        .filter(HistoricalPost.workspace_id == ws_id)
        .order_by(HistoricalPost.views.desc())
        .limit(5)
        .all()
    )
    return {
        "available": True,
        "profile": profile,
        "coverage": artifact.get("coverage"),
        "top_posts": [
            {
                "platform": r.platform,
                "views": r.views,
                "likes": r.likes,
                "comments": r.comments,
                "saves": getattr(r, "saves", 0),
                "follows": getattr(r, "follows", 0),
                "caption": (r.caption or "")[:180],
                "title": r.title,
                "published_at": r.published_at,
            }
            for r in rows
        ],
        "note": "The profile is the median of the top quartile of your posts by growth index.",
    }


# ------------------------------------------------------------------ voice


@router.post("/voice/train")
def train_voice(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return voice_model.train(db, ws_id)


@router.get("/voice/status")
def voice_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return voice_model.status(ws_id)


@router.post("/voice/write")
def write(payload: WriteIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    return voice_model.generate(
        ws_id,
        topic=payload.topic,
        platform=platform,
        kind=payload.kind,
        count=payload.count,
        temperature=payload.temperature,
    )


@router.post("/voice/hooks")
def hooks(payload: HookIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return voice_model.hook_ideas(ws_id, topic=payload.topic, count=payload.count)
