from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.video import AnalysisJob, AnalysisResult, Video
from ..services.text_service import analyze_caption, analyze_hook
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _result_payload(job: AnalysisJob, res: AnalysisResult | None) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error": job.error,
        "video_id": job.video_id,
        "created_at": job.created_at,
        "result": {
            "technical": res.technical,
            "hook": res.hook,
            "metadata_analysis": res.metadata_analysis,
            "recommendations": res.recommendations,
        } if res else None,
    }


@router.get("/video/{video_id}")
def video_analysis(video_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    video = db.query(Video).filter(Video.id == video_id, Video.workspace_id == ws_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.video_id == video_id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(404, "No analysis has been run for this video yet")
    res = db.query(AnalysisResult).filter(AnalysisResult.job_id == job.id).first()
    return _result_payload(job, res)


@router.get("/job/{job_id}")
def job_status(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    job = (
        db.query(AnalysisJob)
        .join(Video, Video.id == AnalysisJob.video_id)
        .filter(AnalysisJob.id == job_id, Video.workspace_id == ws_id)
        .first()
    )
    if not job:
        raise HTTPException(404, "Job not found")
    res = db.query(AnalysisResult).filter(AnalysisResult.job_id == job.id).first()
    return _result_payload(job, res)


@router.post("/caption")
def caption_analysis(payload: dict, user=Depends(get_current_user)):
    caption = str(payload.get("caption") or "")
    platform = str(payload.get("platform") or "instagram").lower()
    if platform not in ("instagram", "youtube"):
        raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
    return analyze_caption(caption, platform)


@router.post("/hook")
def hook_analysis(payload: dict, user=Depends(get_current_user)):
    text = str(payload.get("hook_text") or "")
    try:
        duration = float(payload.get("duration") or 3)
    except (TypeError, ValueError):
        raise HTTPException(400, "duration must be a number")
    if duration < 0 or duration > 60:
        raise HTTPException(400, "duration must be between 0 and 60 seconds")
    if len(text) > 600:
        raise HTTPException(400, "hook text is limited to 600 characters")
    return analyze_hook(text, duration)
