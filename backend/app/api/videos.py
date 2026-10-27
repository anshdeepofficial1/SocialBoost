import os
import threading

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.session import get_db
from ..models.video import Video
from ..services.analysis_service import create_job, run_analysis
from ..services.video_service import (
    ALLOWED_CONTENT_TYPES,
    delete_upload,
    delete_video_cascade,
    save_upload,
)
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/videos", tags=["videos"])


def _serialize(v: Video) -> dict:
    return {
        "id": v.id,
        "filename": v.filename,
        "original_name": v.original_name,
        "duration_seconds": v.duration_seconds,
        "width": v.width,
        "height": v.height,
        "fps": v.fps,
        "aspect_ratio": v.aspect_ratio,
        "size_bytes": v.size_bytes,
        "has_audio": v.has_audio,
        "created_at": v.created_at,
    }


def get_owned_video(video_id: str, workspace_id: str, db: Session) -> Video:
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.workspace_id == workspace_id)
        .first()
    )
    if not video:
        raise HTTPException(404, "Video not found")
    return video


@router.post("/upload")
def upload(file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unsupported file type '{file.content_type}'. Upload MP4, MOV, WebM or MKV.")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".mp4", ".mov", ".webm", ".mkv"}:
        raise HTTPException(400, "Unsupported file extension. Upload MP4, MOV, WebM or MKV.")

    try:
        video = save_upload(file, ws_id, db, max_bytes=settings.max_upload_bytes)
    except ValueError as e:
        raise HTTPException(400, str(e))

    job = create_job(db, video.id)
    # Analysis runs in a worker thread with its own session.
    threading.Thread(target=run_analysis, args=(job.id,), daemon=True).start()

    return {"video_id": video.id, "job_id": job.id, "status": job.status}


@router.get("")
def list_videos(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    vids = (
        db.query(Video)
        .filter(Video.workspace_id == ws_id)
        .order_by(Video.created_at.desc())
        .all()
    )
    return [_serialize(v) for v in vids]


@router.get("/{video_id}")
def get_video(video_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    return _serialize(get_owned_video(video_id, ws_id, db))


@router.delete("/{video_id}")
def delete_video(video_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    video = get_owned_video(video_id, ws_id, db)
    path = delete_video_cascade(video, db)
    delete_upload(path)
    return {"deleted": True, "video_id": video_id}
