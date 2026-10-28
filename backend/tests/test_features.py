"""Analysis helpers, dataset import, calendar, drafts and analytics."""

import io


def test_caption_analysis_instagram(app_client, admin):
    r = app_client.post("/analysis/caption", json={"caption": "A short film about editing.", "platform": "instagram"}, headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["caption_score"] <= 100
    assert body["has_cta"] is False
    assert isinstance(body["adjustments"], list)
    assert body["improved_caption"].endswith("Save this for later.")


def test_caption_analysis_youtube_and_validation(app_client, admin):
    r = app_client.post("/analysis/caption", json={"caption": "How I edit fast #reels #tips #editing", "platform": "youtube"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["alternative_titles"]

    bad = app_client.post("/analysis/caption", json={"caption": "x", "platform": "tiktok"}, headers=admin)
    assert bad.status_code == 400


def test_youtube_title_uses_title_rules_and_never_appends_caption_cta(app_client, admin):
    r = app_client.post(
        "/analysis/caption",
        json={"caption": "Five Editing Mistakes Every Creator Should Avoid", "platform": "youtube", "kind": "title"},
        headers=admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["content_kind"] == "youtube_title"
    assert body["title_score"] == body["caption_score"]
    assert body["improved_title"] == "Five Editing Mistakes Every Creator Should Avoid"
    assert not body["improved_title"].endswith("Save this for later.")
    assert body["alternative_titles"]


def test_youtube_description_uses_description_rules_not_title_rules(app_client, admin):
    r = app_client.post(
        "/analysis/caption",
        json={"caption": "Daily video editing tips for creators", "platform": "youtube", "kind": "description"},
        headers=admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("content_kind") != "youtube_title"
    assert body["improved_caption"].endswith("Save this for later.")


def test_hook_analysis_scoring(app_client, admin):
    strong = app_client.post(
        "/analysis/hook",
        json={"hook_text": "Stop making this mistake — here is why your hooks fail", "duration": 2},
        headers=admin,
    )
    assert strong.status_code == 200
    strong_body = strong.json()
    assert strong_body["hook_score"] > 50
    assert strong_body["band"] in ("workable", "strong")
    assert len(strong_body["alternatives"]) == 3

    weak = app_client.post("/analysis/hook", json={"hook_text": "hi", "duration": 6}, headers=admin)
    assert weak.status_code == 200
    assert weak.json()["hook_score"] < strong_body["hook_score"]

    assert app_client.post("/analysis/hook", json={"hook_text": "x", "duration": 999}, headers=admin).status_code == 400
    assert app_client.post("/analysis/hook", json={"hook_text": "x" * 700}, headers=admin).status_code == 400


def test_dataset_import_and_analytics(app_client, admin, sample_csv):
    files = {"file": ("history.csv", io.BytesIO(sample_csv.encode()), "text/csv")}
    r = app_client.post("/datasets/import", files=files, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_imported"] == 24
    assert body["rows_rejected"] == 0
    assert body["total_rows_in_file"] == 24

    imports = app_client.get("/datasets/imports", headers=admin).json()
    assert imports and imports[0]["rows_imported"] == 24

    summary = app_client.get("/analytics/summary", headers=admin).json()
    assert summary["historical_posts"] == 24
    assert summary["total_views"] > 0
    assert summary["engagement_rate"] > 0

    posts = app_client.get("/analytics/posts", headers=admin).json()
    assert len(posts) == 24
    assert all({"platform", "views", "engagement_rate"} <= set(p) for p in posts)

    # Connected account statistics now derive from imported history.
    app_client.post("/social/accounts", json={"platform": "instagram", "handle": "stats.probe"}, headers=admin)
    accounts = app_client.get("/social/accounts", headers=admin).json()
    ig = next(a for a in accounts if a["platform"] == "instagram")
    assert ig["post_count"] == 12
    assert ig["evidence"].startswith("Derived from imported")


def test_dataset_import_rejects_bad_files(app_client, admin):
    missing = app_client.post(
        "/datasets/import",
        files={"file": ("x.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")},
        headers=admin,
    )
    assert missing.status_code == 400
    assert "missing required" in missing.json()["detail"].lower()

    empty = app_client.post("/datasets/import", files={"file": ("x.csv", io.BytesIO(b""), "text/csv")}, headers=admin)
    assert empty.status_code == 400

    wrong_ext = app_client.post("/datasets/import", files={"file": ("x.txt", io.BytesIO(b"a,b\n1,2\n"), "text/plain")}, headers=admin)
    assert wrong_ext.status_code == 400

    no_valid_rows = app_client.post(
        "/datasets/import",
        files={"file": ("x.csv", io.BytesIO(b"platform,published_at,views\ntiktok,2026-01-01,10\n"), "text/csv")},
        headers=admin,
    )
    assert no_valid_rows.status_code == 400


def test_calendar_lifecycle(app_client, admin):
    created = app_client.post(
        "/calendar/schedule",
        json={"platform": "youtube", "scheduled_at": "2031-02-03T09:30:00Z", "title": "Launch", "caption": "Go live", "is_sandbox": True},
        headers=admin,
    )
    assert created.status_code == 200
    post = created.json()
    assert post["status"] == "scheduled"
    assert post["is_sandbox"] is True

    updated = app_client.put(
        f"/calendar/{post['id']}",
        json={"platform": "instagram", "scheduled_at": "2031-02-04T09:30:00Z", "title": "Launch v2"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["platform"] == "instagram"
    assert updated.json()["title"] == "Launch v2"

    cancelled = app_client.post(f"/calendar/{post['id']}/cancel", headers=admin)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # Cancelled posts are not editable.
    again = app_client.post(f"/calendar/{post['id']}/cancel", headers=admin)
    assert again.status_code == 400


def test_calendar_validation(app_client, admin):
    bad_platform = app_client.post(
        "/calendar/schedule",
        json={"platform": "tiktok", "scheduled_at": "2031-01-01T00:00:00Z"},
        headers=admin,
    )
    assert bad_platform.status_code == 400

    bad_date = app_client.post(
        "/calendar/schedule",
        json={"platform": "instagram", "scheduled_at": "not-a-date"},
        headers=admin,
    )
    assert bad_date.status_code == 400

    missing_video = app_client.post(
        "/calendar/schedule",
        json={"platform": "instagram", "scheduled_at": "2031-01-01T00:00:00Z", "video_id": "nope"},
        headers=admin,
    )
    assert missing_video.status_code == 404


def test_drafts_crud(app_client, admin):
    created = app_client.post(
        "/drafts",
        json={"platform": "instagram", "caption": "First draft", "title": "T", "hashtags": "#a"},
        headers=admin,
    )
    assert created.status_code == 200
    draft = created.json()

    listed = app_client.get("/drafts", headers=admin).json()
    assert any(d["id"] == draft["id"] for d in listed)

    updated = app_client.put(
        f"/drafts/{draft['id']}",
        json={"platform": "youtube", "caption": "Second draft"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["caption"] == "Second draft"
    assert updated.json()["platform"] == "youtube"

    assert app_client.delete(f"/drafts/{draft['id']}", headers=admin).status_code == 200
    assert all(d["id"] != draft["id"] for d in app_client.get("/drafts", headers=admin).json())


def test_drafts_validation_and_isolation(app_client, admin, other_user):
    assert app_client.post("/drafts", json={"platform": "tiktok"}, headers=admin).status_code == 400
    created = app_client.post("/drafts", json={"platform": "instagram", "caption": "private"}, headers=admin).json()
    assert all(d["id"] != created["id"] for d in app_client.get("/drafts", headers=other_user).json())
    assert app_client.put(f"/drafts/{created['id']}", json={"platform": "instagram"}, headers=other_user).status_code == 404


def test_settings_preferences(app_client, admin):
    current = app_client.get("/settings/preferences", headers=admin)
    assert current.status_code == 200
    updated = app_client.put(
        "/settings/preferences",
        json={"timezone": "Europe/London", "platforms": "instagram,youtube", "target_audience": "founders"},
        headers=admin,
    )
    assert updated.status_code == 200
    after = app_client.get("/settings/preferences", headers=admin).json()
    assert after["timezone"] == "Europe/London"
    assert after["target_audience"] == "founders"
