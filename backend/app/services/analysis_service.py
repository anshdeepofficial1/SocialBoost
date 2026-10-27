"""Video analysis pipeline.

Every value written to the report is measured from the uploaded file or
explicitly marked as unavailable. The pipeline never claims to have run a
capability that is missing from the installation (speech recognition, OCR
binaries) and never reports a made-up number.
"""

import logging
import os

import cv2
import numpy as np
from sqlalchemy.orm import Session

from ..models.video import AnalysisJob, AnalysisResult, Video
from . import ml_service

log = logging.getLogger("socialboost.analysis")


def create_job(db: Session, video_id: str) -> AnalysisJob:
    job = AnalysisJob(video_id=video_id, status="queued", progress=0, current_step="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _sample_frames(cap, n: int = 8):
    frames = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        return frames
    idxs = np.linspace(0, max(total - 1, 0), min(n, total), dtype=int)
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if ok:
            frames.append((int(i), frame))
    return frames


def _ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _measure(cap, frames) -> dict:
    brightness: list[float] = []
    contrast: list[float] = []
    black = 0
    for _, frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean = float(gray.mean())
        brightness.append(mean)
        contrast.append(float(gray.std()))
        if mean < 12:
            black += 1

    scene_changes = 0
    prev = None
    sample_n = min(60, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(sample_n):
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diff = float(np.mean(np.abs(gray.astype(float) - prev.astype(float))))
            if diff > 25:
                scene_changes += 1
        prev = gray

    return {
        "avg_brightness": round(float(np.mean(brightness)) if brightness else 0.0, 2),
        "avg_contrast": round(float(np.mean(contrast)) if contrast else 0.0, 2),
        "scene_changes_sampled": scene_changes,
        "frame_samples": len(frames),
        "black_frames": black,
    }


def _hook_report(technical: dict, ocr_text: list[str], ocr_available: bool) -> dict:
    """Rule-based opening assessment with its basis stated explicitly."""
    basis: list[str] = []
    score = 50

    if ocr_text:
        opening = " ".join(ocr_text[:2])[:200]
        if len(opening) > 20:
            score += 10
            basis.append("+10 on-screen text longer than 20 characters")
        if "?" in opening:
            score += 5
            basis.append("+5 on-screen text asks a question")
    else:
        opening = ""

    ratio = technical.get("aspect_ratio")
    if ratio in ("9:16", "1080:1920"):
        score += 5
        basis.append("+5 vertical framing suits Reels/Shorts")
    else:
        basis.append("0 framing is not 9:16")

    duration = technical.get("duration_seconds") or 0
    if 5 <= duration <= 60:
        score += 5
        basis.append("+5 duration is inside the short-form window")
    elif duration > 90:
        score -= 5
        basis.append("-5 duration exceeds 90 seconds")

    if technical.get("avg_brightness", 0) < 40:
        score -= 10
        basis.append("-10 average brightness below 40/255")

    if not ocr_available:
        basis.append("on-screen text was not read (Tesseract is not installed)")

    return {
        "hook_window_seconds": 3.0,
        "speech_onset_seconds": None,
        "speech_analysis": "unavailable",
        "speech_note": "Speech recognition is not installed in this build; no transcript was produced.",
        "ocr_available": ocr_available,
        "opening_text": opening,
        "ocr_samples": ocr_text,
        "hook_score": max(0, min(100, score)),
        "score_basis": basis,
        "notes": (
            "Score is a transparent rule set over measurable properties of the file, "
            "not a prediction of audience response."
        ),
    }


def _metadata_report(video: Video, technical: dict) -> dict:
    issues: list[str] = []
    ratio_ok = technical.get("aspect_ratio") in ("9:16", "1080:1920", "1:1")
    duration_ok = bool(video.duration_seconds and video.duration_seconds <= 90)
    resolution_ok = int(video.height or 0) >= 720

    if not ratio_ok:
        issues.append("Aspect ratio is not 9:16 or 1:1; Reels and Shorts will crop it.")
    if not duration_ok:
        issues.append("Duration is outside the 90 second short-form window.")
    if not resolution_ok:
        issues.append(f"Resolution is {video.width}x{video.height}; below 720p vertical.")
    if technical.get("avg_brightness", 0) < 50:
        issues.append("Average brightness is low; the footage reads as dark.")
    if technical.get("black_frames", 0) > 0:
        issues.append(f"{technical['black_frames']} sampled frame(s) are effectively black.")

    return {
        "aspect_ratio_ok": ratio_ok,
        "duration_ok": duration_ok,
        "resolution_ok": resolution_ok,
        "issues": issues,
        "checks": {
            "aspect_ratio": technical.get("aspect_ratio") or "unknown",
            "duration_seconds": video.duration_seconds,
            "resolution": f"{video.width}x{video.height}",
            "fps": video.fps,
            "has_audio": bool(video.has_audio),
        },
    }


def _recommendations(meta: dict, hook: dict) -> list[dict]:
    recs: list[dict] = []
    for issue in meta["issues"]:
        recs.append({"area": "technical", "problem": issue, "fix": "Correct the flagged property before publishing.", "evidence": issue})

    if hook.get("hook_score") is not None and hook["hook_score"] < 60:
        recs.append({
            "area": "hook",
            "problem": "The opening does not register as strong on the measured checks.",
            "fix": "Open with a concrete claim or question in the first two seconds and put it on screen.",
            "evidence": "; ".join(hook.get("score_basis", [])[:3]) or "rule-based score below 60",
        })

    prediction = meta.get("prediction")
    if prediction and prediction.get("model_version") not in (None, "none"):
        recs.append({
            "area": "prediction",
            "problem": "Predicted reach comes from your imported history.",
            "fix": "Compare this estimate against the factors with the highest importance before changing the edit.",
            "evidence": f"model {prediction['model_version']}, confidence {prediction.get('confidence')}",
        })

    if not recs:
        recs.append({
            "area": "technical",
            "problem": "No measured defect was found.",
            "fix": "Nothing to correct technically; the remaining unknowns are audience response and the opening line.",
            "evidence": "all technical checks passed",
        })
    return recs


def run_analysis(job_id: str) -> None:
    from ..db.session import SessionLocal

    db = SessionLocal()
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        db.close()
        return

    video = db.query(Video).filter(Video.id == job.video_id).first()
    job.status = "processing"
    job.current_step = "validate media"
    job.progress = 5
    db.commit()

    try:
        if video is None or not os.path.exists(video.path):
            raise FileNotFoundError("The uploaded file is missing from storage.")

        job.current_step = "measure frames"
        job.progress = 20
        db.commit()

        cap = cv2.VideoCapture(video.path)
        if not cap.isOpened():
            cap.release()
            raise ValueError("OpenCV could not decode this file. Re-export it as H.264 MP4.")
        frames = _sample_frames(cap, 10)
        if not frames:
            cap.release()
            raise ValueError("No frames could be read from this file.")
        measurements = _measure(cap, frames)
        cap.release()

        technical = {
            "duration_seconds": video.duration_seconds,
            "width": video.width,
            "height": video.height,
            "fps": video.fps,
            "aspect_ratio": video.aspect_ratio,
            "has_audio": bool(video.has_audio),
            **measurements,
        }
        job.progress = 45
        db.commit()

        job.current_step = "read on-screen text"
        ocr_available = _ocr_available()
        ocr_text: list[str] = []
        if ocr_available:
            import pytesseract

            for _, frame in frames[:4]:
                try:
                    text = pytesseract.image_to_string(frame).strip()
                    if text:
                        ocr_text.append(text)
                except Exception:
                    continue
        job.progress = 60
        db.commit()

        job.current_step = "assess the opening"
        hook = _hook_report(technical, ocr_text, ocr_available)
        job.progress = 72
        db.commit()

        job.current_step = "check technical metadata"
        meta = _metadata_report(video, technical)
        job.progress = 82
        db.commit()

        job.current_step = "score with the workspace model"
        prediction = None
        try:
            prediction = ml_service.predict(
                {"duration_seconds": video.duration_seconds, "caption": "", "title": "", "hashtags": ""},
                "instagram",
                db,
                video.workspace_id,
            )
        except Exception as exc:  # a missing or unreadable model must not fail the report
            log.warning("prediction skipped for job %s: %s", job.id, exc)
        meta["prediction"] = prediction
        job.progress = 90
        db.commit()

        job.current_step = "generate recommendations"
        recs = _recommendations(meta, hook)
        job.progress = 95
        db.commit()

        result = AnalysisResult(
            job_id=job.id,
            technical=technical,
            hook=hook,
            metadata_analysis=meta,
            recommendations=recs,
        )
        db.add(result)
        job.status = "done"
        job.current_step = "done"
        job.progress = 100
        job.error = None
        db.commit()
    except Exception as exc:
        log.exception("analysis job %s failed", job.id)
        db.rollback()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            job.current_step = "failed"
            db.commit()
    finally:
        db.close()
