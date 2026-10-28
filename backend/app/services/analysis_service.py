"""Video analysis pipeline.

Every value written to the report is measured from the uploaded file or
explicitly marked as unavailable. The pipeline never claims to have run a
capability that is missing from the installation (speech recognition, OCR
binaries) and never reports a made-up number.
"""

import logging
import os
import re
import threading

import cv2
import numpy as np
from sqlalchemy.orm import Session

from ..models.video import AnalysisJob, AnalysisResult, Video
from . import ml_service
from .video_service import has_audio_stream

log = logging.getLogger("socialboost.analysis")

_OCR_ENGINE = None
_OCR_INIT_ATTEMPTED = False
_OCR_LOCK = threading.Lock()
_WHISPER_MODEL = None
_WHISPER_INIT_ATTEMPTED = False
_WHISPER_LOCK = threading.Lock()


def _sample_opening_frames(path: str, seconds: float = 3.0, n: int = 8):
    """Sample frames only from the actual opening window, with timestamps."""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return []
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            return []
        last = min(total - 1, max(0, int(fps * seconds)) if fps > 0 else min(total - 1, n - 1))
        indices = np.unique(np.linspace(0, last, min(n, last + 1), dtype=int))
        frames = []
        for index in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = cap.read()
            if ok:
                frames.append((float(index / fps) if fps > 0 else 0.0, frame))
        return frames
    finally:
        cap.release()


def _get_ocr_engine():
    global _OCR_ENGINE, _OCR_INIT_ATTEMPTED
    if _OCR_INIT_ATTEMPTED:
        return _OCR_ENGINE
    with _OCR_LOCK:
        if _OCR_INIT_ATTEMPTED:
            return _OCR_ENGINE
        _OCR_INIT_ATTEMPTED = True
        try:
            from rapidocr_onnxruntime import RapidOCR

            _OCR_ENGINE = RapidOCR()
            log.info("RapidOCR engine initialised")
        except Exception:
            log.warning("RapidOCR is unavailable; trying the optional Tesseract fallback", exc_info=True)
            _OCR_ENGINE = None
    return _OCR_ENGINE


def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False



def _ocr_available() -> bool:
    return _get_ocr_engine() is not None or _tesseract_available()


def _extract_ocr_text(opening_frames: list[tuple[float, object]]) -> tuple[list[dict], bool, str]:
    """Read opening-frame text with confidence scores and on-video timestamps."""
    engine = _get_ocr_engine()
    items: list[dict] = []
    seen: set[str] = set()
    if engine is not None:
        successful_calls = 0
        for timestamp, frame in opening_frames:
            try:
                result, _ = engine(frame)
                successful_calls += 1
                for line in result or []:
                    if not isinstance(line, (tuple, list)) or len(line) < 3:
                        continue
                    text = re.sub(r"\s+", " ", str(line[1] or "")).strip()
                    try:
                        confidence = float(line[2])
                    except (TypeError, ValueError):
                        confidence = 0.0
                    normalised = re.sub(r"\W+", "", text).casefold()
                    if not text or confidence < 0.28 or not normalised or normalised in seen:
                        continue
                    seen.add(normalised)
                    items.append({
                        "text": text,
                        "time_seconds": round(float(timestamp), 2),
                        "confidence": round(min(1.0, max(0.0, confidence)), 3),
                    })
            except Exception:
                log.debug("RapidOCR failed on one opening frame", exc_info=True)
        if successful_calls:
            items.sort(key=lambda row: row["time_seconds"])
            return items, True, "RapidOCR"

    if _tesseract_available():
        import pytesseract

        for timestamp, frame in opening_frames:
            try:
                text = re.sub(r"\s+", " ", pytesseract.image_to_string(frame)).strip()
            except Exception:
                continue
            normalised = re.sub(r"\W+", "", text).casefold()
            if text and normalised and normalised not in seen:
                seen.add(normalised)
                items.append({
                    "text": text,
                    "time_seconds": round(float(timestamp), 2),
                    "confidence": None,
                })
        items.sort(key=lambda row: row["time_seconds"])
        return items, True, "Tesseract"
    return [], False, "unavailable"


def _get_whisper_model():
    global _WHISPER_MODEL, _WHISPER_INIT_ATTEMPTED
    if _WHISPER_INIT_ATTEMPTED:
        return _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_INIT_ATTEMPTED:
            return _WHISPER_MODEL
        _WHISPER_INIT_ATTEMPTED = True
        try:
            from faster_whisper import WhisperModel

            model_name = os.getenv("WHISPER_MODEL", "tiny").strip() or "tiny"
            threads = max(1, min(4, os.cpu_count() or 2))
            _WHISPER_MODEL = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=threads,
                num_workers=1,
            )
            log.info("faster-whisper model initialised (model=%s, device=cpu, compute_type=int8)", model_name)
        except Exception:
            log.warning("faster-whisper model could not be initialised", exc_info=True)
            _WHISPER_MODEL = None
    return _WHISPER_MODEL


def _transcribe_speech(path: str, has_audio: bool, media_duration: float = 0.0) -> dict:
    """Transcribe speech locally with faster-whisper; no external inference API is used."""
    if not has_audio:
        return {
            "status": "no_audio",
            "transcript": "",
            "segments": [],
            "language": None,
            "language_probability": None,
            "speech_onset_seconds": None,
            "truncated": False,
            "note": "No audio stream was detected in this video.",
        }
    model = _get_whisper_model()
    if model is None:
        return {
            "status": "unavailable",
            "transcript": "",
            "segments": [],
            "language": None,
            "language_probability": None,
            "speech_onset_seconds": None,
            "truncated": False,
            "note": "Local speech recognition could not initialise. Check the faster-whisper install and backend memory limits.",
        }
    try:
        max_seconds = max(30, min(int(os.getenv("WHISPER_MAX_SECONDS", "180")), 900))
        segments, info = model.transcribe(
            path,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            clip_timestamps=[0, max_seconds],
        )
        rows = []
        for segment in segments:
            text = re.sub(r"\s+", " ", str(segment.text or "")).strip()
            if not text:
                continue
            rows.append({
                "start": round(float(segment.start), 2),
                "end": round(float(segment.end), 2),
                "text": text,
            })
            if len(rows) >= 180:
                break
        transcript = " ".join(row["text"] for row in rows)[:12000]
        onset = rows[0]["start"] if rows else None
        truncated = bool(media_duration > max_seconds and rows and rows[-1]["end"] >= max_seconds - 1)
        if rows:
            note = (
                f"Transcribed locally with faster-whisper; analysis is limited to the first {max_seconds} seconds."
                if truncated else "Transcribed locally with faster-whisper."
            )
            status = "done"
        else:
            note = "Audio was present, but no speech was confidently detected in the processed section."
            status = "no_speech"
        return {
            "status": status,
            "transcript": transcript,
            "segments": rows,
            "language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "speech_onset_seconds": onset,
            "truncated": truncated,
            "note": note,
        }
    except Exception as exc:
        log.warning("Local speech transcription failed for %s (%s)", os.path.basename(path), type(exc).__name__, exc_info=True)
        return {
            "status": "unavailable",
            "transcript": "",
            "segments": [],
            "language": None,
            "language_probability": None,
            "speech_onset_seconds": None,
            "truncated": False,
            "note": "Speech transcription failed for this file. Check the backend logs for the decoder/model error.",
        }


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


def _hook_report(
    technical: dict,
    ocr_items: list[dict],
    ocr_available: bool,
    ocr_engine: str,
    speech: dict,
) -> dict:
    """Combine timestamped on-screen text and local speech transcription."""
    basis: list[str] = []
    score = 50
    ocr_text = [str(item.get("text") or "").strip() for item in ocr_items if str(item.get("text") or "").strip()]
    opening = " ".join(ocr_text[:3])[:280]

    if opening:
        if len(opening) > 20:
            score += 10
            basis.append("+10 readable opening text longer than 20 characters")
        if "?" in opening:
            score += 5
            basis.append("+5 opening text asks a question")

    speech_segments = speech.get("segments") or []
    transcript = speech.get("transcript") or ""
    speech_onset = speech.get("speech_onset_seconds")
    if speech_onset is not None:
        if speech_onset <= 1.5:
            score += 5
            basis.append("+5 speech starts in the first 1.5 seconds")
        elif speech_onset > 2.5:
            score -= 5
            basis.append("-5 first detected speech starts after 2.5 seconds")

    if transcript and ocr_items:
        def words(value: str) -> set[str]:
            return {word.casefold() for word in re.findall(r"[^\W_]{3,}", value, flags=re.UNICODE)}

        alignments = []
        for item in ocr_items:
            text = str(item.get("text") or "")
            timestamp = float(item.get("time_seconds") or 0.0)
            text_words = words(text)
            nearby = [
                segment for segment in speech_segments
                if float(segment.get("start", 0)) <= timestamp + 1.25
                and float(segment.get("end", 0)) >= max(0.0, timestamp - 1.25)
            ]
            spoken_text = " ".join(str(segment.get("text") or "") for segment in nearby)
            overlap = text_words.intersection(words(spoken_text))
            alignments.append({
                **item,
                "spoken_match": bool(overlap) if nearby and text_words else False,
                "nearby_speech": spoken_text[:240],
                "matched_words": sorted(overlap)[:10],
            })
    else:
        alignments = [
            {
                **item,
                "spoken_match": None,
                "nearby_speech": "",
                "matched_words": [],
            }
            for item in ocr_items
        ]

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
        basis.append("on-screen text unavailable: the OCR engine could not initialise")
    elif not ocr_text:
        basis.append("OCR ran on opening frames but did not find readable overlay text")

    if speech.get("status") == "unavailable":
        basis.append("speech recognition could not initialise or decode this audio")
    elif speech.get("status") == "no_audio":
        basis.append("no audio stream was found")
    elif speech.get("status") == "no_speech":
        basis.append("audio was present but speech was not confidently detected")

    return {
        "hook_window_seconds": 3.0,
        "speech_onset_seconds": speech_onset,
        "speech_analysis": speech.get("status") or "unavailable",
        "speech_note": speech.get("note") or "Speech transcription result unavailable.",
        "speech_transcript": transcript,
        "speech_segments": speech_segments,
        "speech_language": speech.get("language"),
        "speech_language_probability": speech.get("language_probability"),
        "speech_transcript_truncated": bool(speech.get("truncated")),
        "ocr_available": ocr_available,
        "ocr_engine": ocr_engine,
        "opening_text": opening,
        "ocr_samples": ocr_text,
        "ocr_segments": ocr_items,
        "screen_text_alignment": alignments,
        "hook_score": max(0, min(100, score)),
        "score_basis": basis,
        "notes": (
            "The hook score is a transparent heuristic based on measured opening text, speech timing, "
            "framing and brightness. It is not a learned prediction of audience response."
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

        # Update older uploads too: they may have been marked silent before
        # audio stream probing was added to the upload pipeline.
        audio_present = has_audio_stream(video.path)
        video.has_audio = audio_present
        technical = {
            "duration_seconds": video.duration_seconds,
            "width": video.width,
            "height": video.height,
            "fps": video.fps,
            "aspect_ratio": video.aspect_ratio,
            "has_audio": audio_present,
            **measurements,
        }
        job.progress = 45
        db.commit()

        job.current_step = "read on-screen text"
        opening_frames = _sample_opening_frames(video.path, seconds=3.0, n=8)
        ocr_items, ocr_available, ocr_engine = _extract_ocr_text(opening_frames)
        ocr_text = [str(item.get("text") or "") for item in ocr_items if item.get("text")]
        job.progress = 56
        db.commit()

        job.current_step = "transcribe speech"
        speech = _transcribe_speech(video.path, audio_present, float(video.duration_seconds or 0))
        job.progress = 68
        db.commit()

        job.current_step = "assess the opening"
        hook = _hook_report(technical, ocr_items, ocr_available, ocr_engine, speech)
        job.progress = 76
        db.commit()

        job.current_step = "check technical metadata"
        meta = _metadata_report(video, technical)
        job.progress = 82
        db.commit()

        job.current_step = "score with the workspace model"
        prediction_features = {
            "duration_seconds": video.duration_seconds,
            "caption": (speech.get("transcript") or "")[:12000],
            "title": hook.get("opening_text") or "",
            "hashtags": " ".join(re.findall(r"#[\\w]+", (speech.get("transcript") or "") + " " + " ".join(ocr_text))),
        }
        predictions = {}
        for platform in ("instagram", "youtube"):
            try:
                predictions[platform] = ml_service.predict(
                    prediction_features,
                    platform,
                    db,
                    video.workspace_id,
                )
            except Exception as exc:  # a missing or unreadable model must not fail the report
                log.warning("prediction skipped for job %s and %s: %s", job.id, platform, exc)
                predictions[platform] = None
        meta["prediction"] = predictions.get("instagram")
        meta["predictions_by_platform"] = predictions
        job.progress = 91
        db.commit()

        job.current_step = "generate recommendations"
        recs = _recommendations(meta, hook)
        job.progress = 97
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
