from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import ScheduledPost
from ..models.video import Video
from ..services.scheduler_service import cancel_job, schedule_post
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/calendar", tags=["calendar"])

PLATFORMS = {"instagram", "youtube"}
EDITABLE_STATUSES = {"scheduled"}


class ScheduleIn(BaseModel):
    video_id: str | None = None
    platform: str = "instagram"
    scheduled_at: str
    caption: str = Field(default="", max_length=2200)
    title: str = Field(default="", max_length=200)
    is_sandbox: bool = True


def _parse_when(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "scheduled_at must be an ISO-8601 date-time")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize(p: ScheduledPost) -> dict:
    return {
        "id": p.id,
        "video_id": p.video_id,
        "platform": p.platform,
        "scheduled_at": p.scheduled_at,
        "status": p.status,
        "caption": p.caption,
        "title": p.title,
        "is_sandbox": p.is_sandbox,
        "attempts": p.attempts,
        "last_error": p.last_error,
        "created_at": p.created_at,
    }


def _validate_video(video_id: str | None, workspace_id: str, db: Session) -> None:
    if not video_id:
        return
    exists = db.query(Video).filter(Video.id == video_id, Video.workspace_id == workspace_id).first()
    if not exists:
        raise HTTPException(404, "Video not found in this workspace")


@router.get("/events")
def events(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    posts = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.workspace_id == ws_id)
        .order_by(ScheduledPost.scheduled_at.asc())
        .all()
    )
    return [_serialize(p) for p in posts]


@router.post("/schedule")
def schedule(payload: ScheduleIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    _validate_video(payload.video_id, ws_id, db)

    post = ScheduledPost(
        workspace_id=ws_id,
        video_id=payload.video_id or None,
        platform=platform,
        scheduled_at=_parse_when(payload.scheduled_at),
        caption=payload.caption,
        title=payload.title,
        is_sandbox=payload.is_sandbox,
        status="scheduled",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    schedule_post(post)
    return _serialize(post)


@router.post("/{post_id}/cancel")
def cancel(post_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.workspace_id == ws_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Scheduled post not found")
    if post.status not in EDITABLE_STATUSES:
        raise HTTPException(400, f"Cannot cancel a post with status '{post.status}'")
    post.status = "cancelled"
    db.commit()
    cancel_job(post.id)
    return _serialize(post)


@router.put("/{post_id}")
def update(post_id: str, payload: ScheduleIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.workspace_id == ws_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Scheduled post not found")
    if post.status not in EDITABLE_STATUSES:
        raise HTTPException(400, f"Cannot edit a post with status '{post.status}'")

    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    _validate_video(payload.video_id, ws_id, db)

    post.platform = platform
    post.video_id = payload.video_id or None
    post.scheduled_at = _parse_when(payload.scheduled_at)
    post.caption = payload.caption
    post.title = payload.title
    post.is_sandbox = payload.is_sandbox
    post.status = "scheduled"
    db.commit()
    db.refresh(post)
    schedule_post(post)
    return _serialize(post)


@router.delete("/{post_id}")
def remove(post_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.workspace_id == ws_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Scheduled post not found")
    cancel_job(post.id)
    db.delete(post)
    db.commit()
    return {"deleted": True, "id": post_id}
