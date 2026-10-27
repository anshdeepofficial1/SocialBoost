"""End-to-end walkthrough against a live backend, on a throwaway account.

Exercises exactly what the frontend calls (see frontend/src/lib/api.ts) plus a
few negative checks that confirm the API refuses to invent data.
"""

import datetime
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
UPLOAD_SRC = r"C:\Users\varun\Documents\Default Project\uploads\d8b73762-f348-48fc-89d6-1562a6316479.mp4"

results: list[tuple[str, str, str]] = []


def ok(r, expect=(200,)):
    if r.status_code not in expect:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:240]}")
    try:
        return r.json()
    except Exception:
        return r.text


def step(name, fn):
    try:
        out = fn()
        results.append((name, "PASS", out))
        return out
    except Exception as e:  # noqa: BLE001
        results.append((name, "FAIL", f"{type(e).__name__}: {e}"))
        return None


def brief(value, n=150):
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    s = " ".join(s.split())
    return s[:n]


client = httpx.Client(base_url=BASE, timeout=120.0)

ts = datetime.datetime.now().strftime("%H%M%S")
email = f"walkthrough+{ts}@signal.test"
password = "walkthrough123"
print(f"== throwaway account: {email} ==\n")

auth = step("auth signup", lambda: ok(client.post("/auth/signup", json={
    "email": email, "password": password, "full_name": "Walkthrough"}), (200,)))
if not auth:
    for n, s, d in results:
        print(f"{s:4} {n:34} {brief(d)}")
    sys.exit(1)
client.headers["Authorization"] = f"Bearer {auth['access_token']}"

step("auth me", lambda: ok(client.get("/auth/me")))

# ---------------------------------------------------------------- upload + analyse
def upload_and_wait():
    with open(UPLOAD_SRC, "rb") as fh:
        d = ok(client.post("/videos/upload", files={"file": ("walkthrough.mp4", fh, "video/mp4")}))
    job_id = d["job_id"]
    for _ in range(240):
        s = ok(client.get(f"/analysis/job/{job_id}"))
        if s["status"] in ("done", "failed", "error"):
            return {"video_id": d["video_id"], "job_status": s["status"], "job": s}
        time.sleep(0.5)
    raise RuntimeError("analysis did not finish within 120s")


uploaded = step("videos/upload + analysis job", upload_and_wait)
video_id = uploaded["video_id"] if uploaded else None

step("videos list", lambda: ok(client.get("/videos")))
step("videos/{id}", lambda: ok(client.get(f"/videos/{video_id}")) if video_id else None)


def analysis_payload():
    d = ok(client.get(f"/analysis/video/{video_id}"))
    res = d.get("result") or {}
    hook = res.get("hook") or {}
    return {
        "status": d.get("status"),
        "has_technical": bool(res.get("technical")),
        "has_hook": bool(hook),
        "speech_onset": hook.get("speech_onset_seconds"),
        "speech_analysis": hook.get("speech_analysis"),
        "ocr_available": hook.get("ocr_available"),
        "recommendations": len(res.get("recommendations") or []),
    }


step("analysis/video/{id}", analysis_payload)

step("analysis/hook", lambda: ok(client.post("/analysis/hook", json={
    "hook_text": "Nobody tells you this about hooks, and it costs you views.", "duration": 3.0})))
step("analysis/caption", lambda: ok(client.post("/analysis/caption", json={
    "caption": "The three-step hook fix #reels #growth", "platform": "instagram"})))

# ---------------------------------------------------------------- datasets
CSV_HEADER = ("post_id,platform,published_at,content_type,duration_seconds,views,likes,"
              "comments,shares,saves,followers_at_publish,caption,title,hashtags,content_category\n")
rows = []
for i in range(12):
    plat = "instagram" if i % 2 == 0 else "youtube"
    day = (datetime.date(2026, 3, 1) + datetime.timedelta(days=i * 3)).isoformat() + "T18:30:00Z"
    rows.append(
        f"wt-{ts}-{i},{plat},{day},{'reel' if plat == 'instagram' else 'short'},"
        f"{12 + i},{5000 + i * 3500},{300 + i * 90},{40 + i * 4},{10 + i},{5 + i},1200,"
        f"\"Walkthrough caption {i} #hooks #reels\",\"Walkthrough title {i}\",#hooks #reels,education"
    )
CSV = CSV_HEADER + "\n".join(rows) + "\n"

step("datasets/import (12 rows)", lambda: ok(client.post(
    "/datasets/import", files={"file": ("walkthrough-history.csv", CSV.encode(), "text/csv")})))
step("datasets/imports", lambda: ok(client.get("/datasets/imports")))


def template():
    r = client.get("/datasets/template")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return {"bytes": len(r.content), "ctype": r.headers.get("content-type", "")}


step("datasets/template", template)

# ---------------------------------------------------------------- predictions
step("predictions/model BEFORE train", lambda: ok(client.get("/predictions/model")))


def predict_before():
    d = ok(client.post("/predictions/run", json={
        "platform": "instagram", "caption": "Walkthrough", "duration_seconds": 20}))
    return {"score": d.get("performance_score"), "category": d.get("category"),
            "model_version": d.get("model_version"), "note": brief(d.get("note"), 120)}


before = step("predictions/run BEFORE train", predict_before)

step("predictions/train", lambda: ok(client.post("/predictions/train")))
step("predictions/model AFTER train", lambda: ok(client.get("/predictions/model")))
step("predictions/status", lambda: ok(client.get("/predictions/status")))


def predict_after():
    payload = {"platform": "instagram", "caption": "Walkthrough hook #reels",
               "duration_seconds": 22}
    if video_id:
        payload["video_id"] = video_id
    d = ok(client.post("/predictions/run", json=payload))
    return {"score": d.get("performance_score"),
            "range": [d.get("expected_views_low"), d.get("expected_views_high")],
            "confidence": d.get("confidence"), "factors": len(d.get("factors") or []),
            "model_version": d.get("model_version")}


step("predictions/run AFTER train", predict_after)
step("predictions history", lambda: len(ok(client.get("/predictions?limit=12"))))

# ---------------------------------------------------------------- calendar
when = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
sched = step("calendar/schedule (sandbox)", lambda: ok(client.post("/calendar/schedule", json={
    "video_id": video_id, "platform": "instagram", "scheduled_at": when,
    "caption": "Walkthrough scheduled post", "title": "Walkthrough", "is_sandbox": True})))
post_id = sched["id"] if isinstance(sched, dict) and "id" in sched else None

step("calendar/events", lambda: ok(client.get("/calendar/events")))
if post_id:
    step("calendar/{id} update", lambda: ok(client.put(f"/calendar/{post_id}", json={
        "video_id": video_id, "platform": "youtube",
        "scheduled_at": when, "caption": "Updated", "title": "Updated", "is_sandbox": True})))
    step("calendar/{id} cancel", lambda: ok(client.post(f"/calendar/{post_id}/cancel")))
    step("calendar/{id} delete", lambda: ok(client.delete(f"/calendar/{post_id}")))

# ---------------------------------------------------------------- drafts
draft = step("drafts create", lambda: ok(client.post("/drafts", json={
    "video_id": video_id, "platform": "instagram", "caption": "Draft caption",
    "title": "Draft title", "hashtags": "#draft"})))
draft_id = draft["id"] if isinstance(draft, dict) and "id" in draft else None
step("drafts list", lambda: ok(client.get("/drafts")))
if draft_id:
    step("drafts update", lambda: ok(client.put(f"/drafts/{draft_id}", json={
        "platform": "instagram", "caption": "Draft caption v2", "title": "Draft title",
        "hashtags": "#draft"})))
    step("drafts delete", lambda: ok(client.delete(f"/drafts/{draft_id}")))

# ---------------------------------------------------------------- analytics / social / settings
step("analytics/summary", lambda: ok(client.get("/analytics/summary")))
step("analytics/posts", lambda: ok(client.get("/analytics/posts")))
step("social/providers", lambda: ok(client.get("/social/providers")))
acc = step("social connect (sandbox IG)", lambda: ok(client.post("/social/accounts", json={
    "platform": "instagram", "handle": "@walkthrough.studio", "display_name": "Walkthrough",
    "mode": "sandbox"})))
acc_id = acc["id"] if isinstance(acc, dict) and "id" in acc else None
step("social/accounts", lambda: ok(client.get("/social/accounts")))
if acc_id:
    step("social/{id}/sync", lambda: ok(client.post(f"/social/accounts/{acc_id}/sync")))
    step("social/summary", lambda: ok(client.get("/social/summary")))
    step("social/{id} disconnect", lambda: ok(client.delete(f"/social/accounts/{acc_id}")))
step("settings/preferences GET", lambda: ok(client.get("/settings/preferences")))
step("settings/preferences PUT", lambda: ok(client.put("/settings/preferences", json={
    "timezone": "Europe/London", "target_audience": "walkthrough"})))
step("integrations/status", lambda: ok(client.get("/integrations/status")))

# ---------------------------------------------------------------- negative checks
def expect_400(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        results.append((name, "FAIL", str(e)))
        return
    results.append((name, "PASS" if r.status_code == 400 else "FAIL",
                    f"HTTP {r.status_code} {brief(r.text, 90)}"))


expect_400("reject bad platform", lambda: client.post("/predictions/run", json={"platform": "tiktok"}))
expect_400("reject bad date", lambda: client.post("/calendar/schedule", json={
    "platform": "instagram", "scheduled_at": "not-a-date"}))
expect_400("reject bad hook duration", lambda: client.post("/analysis/hook", json={
    "hook_text": "hi", "duration": 999}))

# ---------------------------------------------------------------- cleanup via API
if video_id:
    step("videos/{id} delete", lambda: ok(client.delete(f"/videos/{video_id}")))

print("\n=== RESULTS ===")
fails = 0
for n, s, d in results:
    if s == "FAIL":
        fails += 1
    print(f"{s:4} | {n:34} | {brief(d)}")
print(f"\n{len(results) - fails}/{len(results)} passed, {fails} failed")
print(f"CLEANUP_EMAIL={email}")
print(f"CLEANUP_TOKEN={auth['access_token']}")
