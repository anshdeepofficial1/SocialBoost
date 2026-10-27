"""Caption and title drafts.

A draft can be attached to a video or stand alone, and is always scoped to the
workspace that created it.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.prediction import Draft
from ..models.video import Video
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/drafts", tags=["drafts"])

PLATFORMS = {"instagram", "youtube"}


class DraftIn(BaseModel):
    video_id: str | None = None
    platform: str = "instagram"
    caption: str = Field(default="", max_length=2200)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    hashtags: str = Field(default="", max_length=500)


def _serialize(d: Draft) -> dict:
    return {
        "id": d.id,
        "video_id": d.video_id,
        "platform": d.platform,
        "caption": d.caption,
        "title": d.title,
        "description": d.description,
        "hashtags": d.hashtags,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _get_owned(draft_id: str, workspace_id: str, db: Session) -> Draft:
    draft = db.query(Draft).filter(Draft.id == draft_id, Draft.workspace_id == workspace_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


def _validate(payload: DraftIn, workspace_id: str, db: Session) -> str:
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    if payload.video_id:
        exists = (
            db.query(Video)
            .filter(Video.id == payload.video_id, Video.workspace_id == workspace_id)
            .first()
        )
        if not exists:
            raise HTTPException(404, "Video not found in this workspace")
    return platform


@router.get("")
def list_drafts(video_id: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    q = db.query(Draft).filter(Draft.workspace_id == ws_id)
    if video_id:
        q = q.filter(Draft.video_id == video_id)
    rows = q.order_by(Draft.updated_at.desc()).all()
    return [_serialize(d) for d in rows]


@router.post("")
def create_draft(payload: DraftIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    platform = _validate(payload, ws_id, db)
    draft = Draft(
        workspace_id=ws_id,
        video_id=payload.video_id or None,
        platform=platform,
        caption=payload.caption,
        title=payload.title,
        description=payload.description,
        hashtags=payload.hashtags,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _serialize(draft)


@router.put("/{draft_id}")
def update_draft(draft_id: str, payload: DraftIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    draft = _get_owned(draft_id, ws_id, db)
    platform = _validate(payload, ws_id, db)
    draft.video_id = payload.video_id or None
    draft.platform = platform
    draft.caption = payload.caption
    draft.title = payload.title
    draft.description = payload.description
    draft.hashtags = payload.hashtags
    db.commit()
    db.refresh(draft)
    return _serialize(draft)


@router.delete("/{draft_id}")
def delete_draft(draft_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    draft = _get_owned(draft_id, ws_id, db)
    db.delete(draft)
    db.commit()
    return {"deleted": True, "id": draft_id}
