import os
import uuid

import cv2
from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.video import Video

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "application/octet-stream",
}


def save_upload(file: UploadFile, workspace_id: str, db: Session, max_bytes: int | None = None) -> Video:
    upload_dir = settings.resolved_upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    name = f"{uuid.uuid4()}{ext}"
    path = os.path.join(upload_dir, name)
    limit = max_bytes or settings.max_upload_bytes

    written = 0
    try:
        with open(path, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise ValueError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB upload limit.")
                f.write(chunk)
        if written == 0:
            raise ValueError("The uploaded file is empty.")
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise

    video = Video(
        workspace_id=workspace_id,
        filename=name,
        original_name=file.filename or name,
        path=path,
        size_bytes=written,
    )
    _extract_metadata(video, path)

    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def has_audio_stream(path: str) -> bool:
    """Detect an actual audio stream with PyAV instead of assuming every upload is silent."""
    try:
        import av

        with av.open(path) as container:
            return any(stream.type == "audio" for stream in container.streams)
    except Exception:
        # Metadata extraction must remain usable even if a malformed container
        # or unsupported codec prevents probing.
        return False


def _extract_metadata(video: Video, path: str) -> None:
    cap = None
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frame_count / fps if fps else 0.0
        video.fps = float(fps)
        video.width = width
        video.height = height
        video.duration_seconds = float(duration)
        video.aspect_ratio = _reduced_ratio(width, height) if width and height else ""
        video.has_audio = has_audio_stream(path)
    except Exception:
        pass
    finally:
        if cap is not None:
            cap.release()


def _reduced_ratio(width: int, height: int) -> str:
    from math import gcd

    divisor = gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


def delete_upload(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def delete_video_cascade(video: Video, db: Session) -> str:
    """Remove a video and every row that depends on it.

    ORM cascade covers relationship deletes, but the queries below are bulk
    operations, so the children are removed explicitly. Scheduled posts are
    kept and merely detached: the plan to publish survives the file.
    Returns the storage path that the caller should delete.
    """
    from ..models.calendar import ScheduledPost
    from ..models.prediction import Draft, Prediction
    from ..models.video import AnalysisJob, AnalysisResult

    job_ids = [row[0] for row in db.query(AnalysisJob.id).filter(AnalysisJob.video_id == video.id).all()]
    if job_ids:
        db.query(AnalysisResult).filter(AnalysisResult.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(AnalysisJob).filter(AnalysisJob.id.in_(job_ids)).delete(synchronize_session=False)
    db.query(Prediction).filter(Prediction.video_id == video.id).delete(synchronize_session=False)
    db.query(Draft).filter(Draft.video_id == video.id).delete(synchronize_session=False)
    db.query(ScheduledPost).filter(ScheduledPost.video_id == video.id).update(
        {ScheduledPost.video_id: None}, synchronize_session=False
    )

    path = video.path
    db.delete(video)
    db.commit()
    return path
