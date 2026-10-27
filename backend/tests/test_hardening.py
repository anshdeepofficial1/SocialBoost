"""Behaviour added during the backend hardening pass."""

import io


def test_csv_template_downloads(app_client, admin):
    r = app_client.get("/datasets/template", headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    first_line = r.text.splitlines()[0]
    for column in ("post_id", "platform", "published_at", "views"):
        assert column in first_line


def test_reimport_skips_duplicate_post_ids(app_client, admin):
    csv = (
        "post_id,platform,published_at,views,likes\n"
        "dup-1,instagram,2026-03-01T10:00:00Z,1000,50\n"
        "dup-2,youtube,2026-03-02T10:00:00Z,2000,80\n"
    )
    first = app_client.post(
        "/datasets/import", files={"file": ("a.csv", io.BytesIO(csv.encode()), "text/csv")}, headers=admin
    )
    assert first.status_code == 200
    assert first.json()["rows_imported"] == 2

    second = app_client.post(
        "/datasets/import", files={"file": ("a.csv", io.BytesIO(csv.encode()), "text/csv")}, headers=admin
    )
    assert second.status_code == 400  # every row was a duplicate
    assert "No valid rows" in second.json()["detail"]

    mixed = csv + "dup-3,instagram,2026-03-03T10:00:00Z,3000,90\n"
    third = app_client.post(
        "/datasets/import", files={"file": ("b.csv", io.BytesIO(mixed.encode()), "text/csv")}, headers=admin
    )
    assert third.status_code == 200
    assert third.json()["rows_imported"] == 1
    assert third.json()["rows_duplicate"] == 2
    assert third.json()["warnings"]


def test_rows_with_unparseable_dates_are_rejected(app_client, admin):
    csv = "post_id,platform,published_at,views\nbad-1,instagram,not-a-date,1000\nok-1,instagram,2026-04-01T10:00:00Z,1000\n"
    r = app_client.post("/datasets/import", files={"file": ("x.csv", io.BytesIO(csv.encode()), "text/csv")}, headers=admin)
    assert r.status_code == 200
    assert r.json()["rows_imported"] == 1
    assert r.json()["rows_rejected"] == 1


def test_analytics_summary_shape(app_client, admin):
    summary = app_client.get("/analytics/summary", headers=admin).json()
    for key in ("videos", "analyses", "analyses_completed", "historical_posts", "total_views", "engagement_rate", "by_platform", "source"):
        assert key in summary
    assert set(summary["by_platform"]) == {"instagram", "youtube"}
    assert 0 <= summary["engagement_rate"] < 1

    filtered = app_client.get("/analytics/posts?platform=instagram&limit=5", headers=admin)
    assert filtered.status_code == 200
    assert len(filtered.json()) <= 5
    assert all(p["platform"] == "instagram" for p in filtered.json())

    assert app_client.get("/analytics/posts?platform=tiktok", headers=admin).status_code == 400


def test_prediction_history_is_workspace_scoped(app_client, admin, other_user):
    app_client.post("/predictions/run", json={"platform": "youtube", "caption": "history"}, headers=admin)
    mine = app_client.get("/predictions", headers=admin).json()
    assert isinstance(mine, list) and mine
    assert all(p["platform"] == "youtube" for p in mine)
    assert app_client.get("/predictions", headers=other_user).json() == []


def test_prediction_is_persisted_with_its_range(app_client, admin):
    r = app_client.post("/predictions/run", json={"platform": "instagram", "caption": "persisted"}, headers=admin)
    assert r.status_code == 200
    body = r.json()
    history = app_client.get("/predictions", headers=admin).json()
    stored = next(p for p in history if p["id"] == body["prediction_id"])
    assert stored["expected_views_low"] == body["expected_views_low"]
    assert stored["expected_views_high"] == body["expected_views_high"]
    assert stored["performance_score"] == body["performance_score"]
    assert stored["confidence"] == body["confidence"]
    assert stored["model_version"] == body["model_version"]


def test_deleting_a_video_removes_dependent_rows(app_client, admin):
    """Bulk deletes bypass ORM cascades; the API must not leave orphans."""
    from app.db.session import SessionLocal
    from app.models.prediction import Draft, Prediction
    from app.models.video import AnalysisJob, AnalysisResult, Video

    db = SessionLocal()
    try:
        video = Video(workspace_id="orphan-ws", filename="f.mp4", original_name="f.mp4", path="nope.mp4")
        db.add(video)
        db.commit()
        job = AnalysisJob(video_id=video.id, status="done")
        db.add(job)
        db.commit()
        db.add(AnalysisResult(job_id=job.id))
        db.add(Prediction(workspace_id="orphan-ws", video_id=video.id, platform="instagram"))
        db.add(Draft(workspace_id="orphan-ws", video_id=video.id, platform="instagram"))
        db.commit()
        video_id, job_id = video.id, job.id
    finally:
        db.close()

    # Delete through the service layer using a matching workspace row.
    from app.services.video_service import delete_video_cascade

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        delete_video_cascade(video, db)
    finally:
        db.close()

    db = SessionLocal()
    try:
        assert db.query(Video).filter(Video.id == video_id).first() is None
        assert db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first() is None
        assert db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first() is None
        assert db.query(Prediction).filter(Prediction.video_id == video_id).first() is None
        assert db.query(Draft).filter(Draft.video_id == video_id).first() is None
    finally:
        db.close()


def test_settings_reject_invalid_values(app_client, admin):
    assert app_client.put("/settings/preferences", json={"theme": "neon"}, headers=admin).status_code == 400
    assert app_client.put("/settings/preferences", json={"timezone": "Mars/Olympus"}, headers=admin).status_code == 400
    assert app_client.put("/settings/preferences", json={"platforms": "instagram,tiktok"}, headers=admin).status_code == 400

    ok = app_client.put(
        "/settings/preferences",
        json={"platforms": "youtube,instagram,youtube", "theme": "dark"},
        headers=admin,
    )
    assert ok.status_code == 200
    assert ok.json()["platforms"] == "instagram,youtube"
    assert ok.json()["theme"] == "dark"


def test_scheduling_in_the_past_is_accepted_and_runs_as_sandbox(app_client, admin):
    import time

    created = app_client.post(
        "/calendar/schedule",
        json={"platform": "instagram", "scheduled_at": "2020-01-01T00:00:00Z", "is_sandbox": True, "title": "Backfill"},
        headers=admin,
    )
    assert created.status_code == 200
    post_id = created.json()["id"]

    status = None
    for _ in range(20):
        events = app_client.get("/calendar/events", headers=admin).json()
        status = next(e["status"] for e in events if e["id"] == post_id)
        if status != "scheduled":
            break
        time.sleep(0.25)
    assert status == "sandbox", status


def test_scheduled_post_never_claims_published_without_live_publishing(app_client, admin):
    import time

    created = app_client.post(
        "/calendar/schedule",
        json={"platform": "youtube", "scheduled_at": "2020-01-02T00:00:00Z", "is_sandbox": False},
        headers=admin,
    )
    assert created.status_code == 200
    post_id = created.json()["id"]

    event = None
    for _ in range(20):
        events = app_client.get("/calendar/events", headers=admin).json()
        event = next(e for e in events if e["id"] == post_id)
        if event["status"] != "scheduled":
            break
        time.sleep(0.25)
    assert event["status"] == "failed"
    assert "Live publishing is disabled" in event["last_error"]
