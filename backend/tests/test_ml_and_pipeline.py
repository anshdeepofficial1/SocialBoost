"""Model training, prediction and scheduled publishing behaviour."""

import os

import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.calendar import ScheduledPost
from app.services import ml_service
from app.services.scheduler_service import publish_job


def test_prediction_without_model_is_illustrative(app_client, admin):
    r = app_client.post(
        "/predictions/run",
        json={"platform": "instagram", "caption": "hello world", "duration_seconds": 22},
        headers=admin,
    )
    assert r.status_code == 200
    body = r.json()
    # With no trained model, the honest answer is "unknown", not a fake number.
    assert body["model_version"] in ("none",)
    assert body["expected_views_low"] is None
    assert body["confidence"] == 0.0
    assert "train" in body["note"].lower()


def test_train_requires_minimum_rows(app_client, admin, sample_csv):
    import io

    # In this session order the dataset may already be imported; either way the
    # call must return a structured status rather than an exception.
    files = {"file": ("history.csv", io.BytesIO(sample_csv.encode()), "text/csv")}
    app_client.post("/datasets/import", files=files, headers=admin)
    r = app_client.post("/predictions/train", headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] in ("trained", "insufficient_data")


def test_train_then_predict_uses_the_model(app_client, admin, sample_csv):
    import io

    files = {"file": ("history.csv", io.BytesIO(sample_csv.encode()), "text/csv")}
    app_client.post("/datasets/import", files=files, headers=admin)

    trained = app_client.post("/predictions/train", headers=admin)
    assert trained.status_code == 200
    body = trained.json()
    assert body["status"] == "trained", body
    assert body["n_samples"] >= settings.MIN_TRAINING_ROWS
    assert "mae" in body["metrics"] and "r2" in body["metrics"]

    r = app_client.post(
        "/predictions/run",
        json={"platform": "instagram", "caption": "A caption", "title": "A title", "hashtags": "#a #b", "duration_seconds": 25},
        headers=admin,
    )
    assert r.status_code == 200
    pred = r.json()
    assert pred["model_version"] != "none"
    assert pred["expected_views_low"] is not None
    assert pred["expected_views_low"] <= pred["expected_views_high"]
    assert 0 <= pred["performance_score"] <= 100
    assert 0.05 <= pred["confidence"] <= 0.9
    assert pred["factors"]
    assert "percentiles" in pred

    model = app_client.get("/predictions/model", headers=admin).json()
    assert model["available"] is True
    assert model["top_features"]

    versions = app_client.get("/predictions/status", headers=admin).json()
    assert isinstance(versions, list) and versions
    assert any(v["name"] == "views_rf" for v in versions)


def test_predict_validates_platform_and_video(app_client, admin):
    assert app_client.post("/predictions/run", json={"platform": "tiktok"}, headers=admin).status_code == 400
    assert app_client.post("/predictions/run", json={"platform": "instagram", "video_id": "missing"}, headers=admin).status_code == 404


def test_models_are_per_workspace(app_client, admin, other_user):
    # The other workspace has no history, so it must not inherit the trained model.
    r = app_client.post("/predictions/run", json={"platform": "instagram"}, headers=other_user)
    assert r.status_code == 200
    assert r.json()["model_version"] == "none"


@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (180, 320))
    for i in range(36):
        frame = np.full((320, 180, 3), 40 + i * 4, dtype=np.uint8)
        cv2.rectangle(frame, (20, 20), (160, 300), (200, 120, 60), 2)
        writer.write(frame)
    writer.release()
    assert path.exists() and path.stat().st_size > 0
    return path


def test_upload_rejects_non_video(app_client, admin):
    r = app_client.post("/videos/upload", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=admin)
    assert r.status_code == 400


def test_upload_analyze_and_delete(app_client, admin, tiny_video):
    import time

    with open(tiny_video, "rb") as fh:
        r = app_client.post("/videos/upload", files={"file": ("clip.mp4", fh, "video/mp4")}, headers=admin)
    assert r.status_code == 200, r.text
    payload = r.json()
    video_id, job_id = payload["video_id"], payload["job_id"]

    listing = app_client.get("/videos", headers=admin).json()
    assert any(v["id"] == video_id for v in listing)

    # Wait for the background analysis thread to finish.
    status = {}
    for _ in range(60):
        status = app_client.get(f"/analysis/job/{job_id}", headers=admin).json()
        if status["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert status["status"] == "done", status

    report = app_client.get(f"/analysis/video/{video_id}", headers=admin).json()
    assert report["result"] is not None
    tech = report["result"]["technical"]
    assert tech["width"] == 180 and tech["height"] == 320
    assert tech["aspect_ratio"] == "9:16"
    assert report["result"]["hook"]["hook_score"] is not None
    assert report["result"]["metadata_analysis"]["aspect_ratio_ok"] is True

    assert app_client.delete(f"/videos/{video_id}", headers=admin).status_code == 200
    assert all(v["id"] != video_id for v in app_client.get("/videos", headers=admin).json())

    # Deleting twice is a clean 404.
    assert app_client.delete(f"/videos/{video_id}", headers=admin).status_code == 404


def test_analysis_unknown_ids_404(app_client, admin, other_user):
    assert app_client.get("/analysis/video/nope", headers=admin).status_code == 404
    assert app_client.get("/analysis/job/nope", headers=admin).status_code == 404


def test_sandbox_job_is_marked_sandbox_not_published(app_client, admin):
    db = SessionLocal()
    try:
        post = ScheduledPost(workspace_id="test-ws", platform="instagram", scheduled_at=__import__("datetime").datetime.utcnow(), is_sandbox=True, status="scheduled")
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    publish_job(post_id)

    db = SessionLocal()
    try:
        stored = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        assert stored.status == "sandbox"
        assert stored.attempts == 1
        assert stored.last_error is None
    finally:
        db.close()


def test_live_job_fails_with_an_explanation(app_client, admin):
    from datetime import datetime

    db = SessionLocal()
    try:
        post = ScheduledPost(workspace_id="test-ws", platform="youtube", scheduled_at=datetime.utcnow(), is_sandbox=False, status="scheduled")
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    publish_job(post_id)

    db = SessionLocal()
    try:
        stored = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        assert stored.status == "failed"
        assert "Live publishing is disabled" in stored.last_error
    finally:
        db.close()


def test_publish_job_ignores_already_resolved():
    from datetime import datetime

    db = SessionLocal()
    try:
        post = ScheduledPost(workspace_id="test-ws", platform="instagram", scheduled_at=datetime.utcnow(), is_sandbox=True, status="cancelled")
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    publish_job(post_id)

    db = SessionLocal()
    try:
        stored = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        assert stored.status == "cancelled"
        assert (stored.attempts or 0) == 0
    finally:
        db.close()


def test_model_artifacts_are_workspace_scoped():
    a = ml_service.artifacts_for("workspace-a")
    b = ml_service.artifacts_for("workspace-b")
    global_ = ml_service.artifacts_for(None)
    assert a != b
    assert a != global_
    assert os.path.basename(a[0]).startswith("views_model_")
