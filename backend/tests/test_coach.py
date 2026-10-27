"""Real export shapes must import, and both models must learn something useful."""

import io

import pytest

# An Instagram-style export: different names, percentages, thousands separators.
IG_EXPORT = """Media ID,Media Type,Caption,Publish Time,Duration (s),Views,Likes,Comments,Shares,Saves,Reach,Profile Visits,Follows
ig_1,Reel,"How I edit a reel in 30 seconds #editing #reels",2026-01-02T18:30:00Z,24,"18,400",920,64,31,210,"17,200",310,96
ig_2,Reel,"Three mistakes killing your hooks #hooks",2026-01-04T19:00:00Z,18,"9,100",410,22,9,40,"8,300",120,18
ig_3,Reel,"Stop editing like this #editing",2026-01-06T17:45:00Z,31,"24,900",1510,120,66,410,"22,400",520,180
ig_4,Reel,"A quiet day in the studio #vlog",2026-01-08T12:10:00Z,45,"4,200",180,11,4,12,"3,900",40,6
ig_5,Reel,"The truth about posting every day #growth",2026-01-10T20:15:00Z,28,"15,700",880,71,28,190,"14,600",260,84
ig_6,Reel,"Why your reels flop #growth #reels",2026-01-12T18:05:00Z,22,"21,300",1290,98,52,330,"19,800",430,150
ig_7,Reel,"Rate this transition 1-10 #editing",2026-01-14T21:00:00Z,16,"11,800",700,45,17,120,"10,900",190,52
ig_8,Reel,"Nobody talks about this part of editing",2026-01-16T19:20:00Z,26,"19,600",1180,88,44,290,"18,100",380,132
ig_9,Reel,"Save this before you edit again",2026-01-18T18:40:00Z,20,"17,200",1010,77,38,260,"16,000",330,110
ig_10,Reel,"What should I edit next? #editing",2026-01-20T17:30:00Z,14,"7,400",330,19,7,28,"6,800",95,12
ig_11,Reel,"Here is the 3 second rule nobody uses",2026-01-22T19:10:00Z,19,"23,100",1440,112,61,380,"21,500",470,168
ig_12,Reel,"My worst performing edit this month",2026-01-24T13:00:00Z,52,"3,100",120,8,3,8,"2,900",28,4
"""

# A YouTube Studio export: preamble rows, clock durations, percentages.
YT_EXPORT = """Channel: Signal Studio,,,,,,,,,
Video title,Video publish time,Duration,Views,Watch time (hours),Average view duration,Average percentage viewed,Likes,Comments,Subscribers gained
Totals,,,,,,,2400,180,96
Shorts: editing speedrun,"Jan 3, 2026",0:24,15200,101,0:17,70.8%,760,54,44
Shorts: hook mistakes,"Jan 5, 2026",0:18,8100,40,0:14,77.8%,380,22,12
Shorts: stop doing this,"Jan 7, 2026",0:31,20100,180,0:21,67.7%,1100,88,81
Shorts: studio vlog,"Jan 9, 2026",0:45,3600,33,0:19,42.2%,150,9,3
Shorts: posting every day truth,"Jan 11, 2026",0:28,13400,90,0:18,64.3%,720,60,39
Shorts: why shorts flop,"Jan 13, 2026",0:22,18900,150,0:19,86.4%,980,79,66
Shorts: transition rating,"Jan 15, 2026",0:16,10200,55,0:13,81.3%,610,41,21
Shorts: the part nobody mentions,"Jan 17, 2026",0:26,17600,140,0:20,76.9%,1050,74,58
Shorts: save this edit tip,"Jan 19, 2026",0:20,14800,105,0:17,85.0%,900,63,47
Shorts: what next,"Jan 21, 2026",0:14,6200,25,0:11,78.6%,280,17,6
Shorts: the 3 second rule,"Jan 23, 2026",0:19,21400,170,0:18,94.7%,1300,95,74
Shorts: my worst edit,"Jan 25, 2026",0:52,2700,18,0:15,28.8%,110,7,2
"""


def _upload(app_client, auth, content: str, name: str):
    files = {"file": (name, io.BytesIO(content.encode()), "text/csv")}
    return app_client.post("/datasets/import", files=files, headers=auth)


@pytest.fixture(scope="module")
def coach_owner(app_client):
    """A dedicated workspace.

    The shared ``admin`` fixture is used by the older tests, which assert exact
    row counts. Importing into it here would make those tests order-dependent.
    """
    email = "coach@example.com"
    r = app_client.post("/auth/signup", json={"email": email, "password": "pass123", "full_name": "Coach"})
    if r.status_code == 400 and "already" in r.text:
        r = app_client.post("/auth/login", json={"email": email, "password": "pass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_instagram_export_imports_with_currency_and_percentages(app_client, coach_owner):
    r = _upload(app_client, coach_owner, IG_EXPORT, "instagram_export.csv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_imported"] == 12
    assert body["rows_rejected"] == 0
    mapping = body["mapping"]
    assert mapping["detected_platform"] == "instagram"
    # "Media ID" must become post_id, not be ignored.
    assert mapping["mapped"].get("post_id") == "Media ID"
    assert mapping["mapped"].get("saves") == "Saves"
    assert mapping["mapped"].get("follows") == "Follows"


def test_youtube_export_skips_preamble_and_parses_clock(app_client, coach_owner):
    r = _upload(app_client, coach_owner, YT_EXPORT, "youtube_studio.csv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_imported"] == 12
    assert body["mapping"]["preamble_rows_skipped"] == 1
    assert body["mapping"]["detected_platform"] == "youtube"

    posts = app_client.get("/analytics/posts?platform=youtube", headers=coach_owner).json()
    durations = sorted(p["views"] for p in posts)
    assert durations == sorted([15200, 8100, 20100, 3600, 13400, 18900, 10200, 17600, 14800, 6200, 21400, 2700])


def test_coach_trains_and_prescribes(app_client, coach_owner):
    r = app_client.post("/coach/train", headers=coach_owner)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "trained", body
    assert body["n_samples"] == 24
    # Saves and follows are present in both exports, so both must be weighted in.
    assert body["target"]["signals"]["saves"] is True
    assert body["target"]["signals"]["follows"] is True
    assert body["cross_validation"]["folds"] >= 2
    assert body["top_features"]

    score = app_client.post(
        "/coach/score",
        json={
            "platform": "instagram",
            "caption": "How I edit a reel in 20 seconds #editing #reels",
            "hashtags": "#editing #reels",
            "duration_seconds": 22,
        },
        headers=coach_owner,
    )
    assert score.status_code == 200, score.text
    result = score.json()
    assert result["available"] is True
    assert 0 <= result["growth_index"] <= 100
    assert result["range"][0] <= result["growth_index"] <= result["range"][1]
    assert result["levers"], "the coach must prescribe changes, not just score"
    assert all("expected_lift" in lever for lever in result["levers"])
    assert 0.05 <= result["confidence"] <= 0.9
    assert result["percentile_reading"]


def test_coach_without_training_is_explicit(app_client, other_user):
    r = app_client.post("/coach/score", json={"platform": "instagram", "caption": "x"}, headers=other_user)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["growth_index"] is None
    assert "train" in body["note"].lower()


def test_coach_is_workspace_scoped(app_client, coach_owner, other_user):
    assert app_client.get("/coach/status", headers=other_user).json()["available"] is False
    assert app_client.get("/coach/status", headers=coach_owner).json()["available"] is True


def test_voice_writer_learns_the_account_voice(app_client, coach_owner):
    r = app_client.post("/coach/voice/train", headers=coach_owner)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "trained", body
    assert body["n_captions"] >= 8
    style = body["style"]
    assert style["vocabulary_size"] > 20
    assert style["hashtag_pool"]

    written = app_client.post(
        "/coach/voice/write",
        json={"topic": "editing", "platform": "instagram", "count": 3},
        headers=coach_owner,
    )
    assert written.status_code == 200, written.text
    payload = written.json()
    assert payload["available"] is True
    assert len(payload["variants"]) >= 1
    assert all(v["text"] for v in payload["variants"])

    hooks = app_client.post("/coach/voice/hooks", json={"topic": "hooks", "count": 4}, headers=coach_owner)
    assert hooks.status_code == 200
    assert len(hooks.json()["hooks"]) >= 1


def test_voice_writer_without_training_is_explicit(app_client, other_user):
    r = app_client.post("/coach/voice/write", json={"topic": "x"}, headers=other_user)
    assert r.status_code == 200
    assert r.json()["available"] is False
    assert r.json()["variants"] == []


def test_adapter_rejects_unusable_files(app_client, coach_owner):
    r = _upload(app_client, coach_owner, "a,b\n1,2\n", "x.csv")
    assert r.status_code == 400
    assert "missing required" in r.json()["detail"].lower()

    r = _upload(app_client, coach_owner, "platform,published_at,views\ntiktok,2026-01-01,10\n", "y.csv")
    assert r.status_code == 400
