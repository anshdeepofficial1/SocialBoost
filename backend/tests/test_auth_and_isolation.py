"""Health, authentication and workspace isolation."""


def test_health(app_client):
    r = app_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "env" in body


def test_openapi_documents_routes(app_client):
    spec = app_client.get("/openapi.json").json()
    paths = spec["paths"]
    for expected in [
        "/auth/login",
        "/videos",
        "/analysis/caption",
        "/predictions/run",
        "/datasets/import",
        "/calendar/events",
        "/analytics/summary",
        "/social/accounts",
        "/drafts",
        "/integrations/status",
    ]:
        assert expected in paths, f"missing route {expected}"


def test_signup_login_me(app_client):
    r = app_client.post("/auth/signup", json={"email": "flow@example.com", "password": "pass123", "full_name": "Flow"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = app_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"

    login = app_client.post("/auth/login", json={"email": "FLOW@example.com", "password": "pass123"})
    assert login.status_code == 200


def test_signup_validation(app_client):
    dup = app_client.post("/auth/signup", json={"email": "flow@example.com", "password": "pass123"})
    assert dup.status_code == 400

    short = app_client.post("/auth/signup", json={"email": "short@example.com", "password": "123"})
    assert short.status_code == 400
    assert "6 characters" in short.json()["detail"]

    bad = app_client.post("/auth/signup", json={"email": "not-an-email", "password": "pass123"})
    assert bad.status_code == 400

    # bcrypt silently truncates past 72 bytes; the API must refuse instead.
    too_long = app_client.post("/auth/signup", json={"email": "long@example.com", "password": "a" * 100})
    assert too_long.status_code == 400
    assert "72 bytes" in too_long.json()["detail"]


def test_login_wrong_password(app_client):
    r = app_client.post("/auth/login", json={"email": "flow@example.com", "password": "nope"})
    assert r.status_code == 400


def test_protected_routes_require_auth(app_client):
    for path in ["/auth/me", "/videos", "/calendar/events", "/analytics/summary", "/social/accounts", "/drafts"]:
        assert app_client.get(path).status_code == 401, path


def test_rejects_tampered_token(app_client):
    r = app_client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


def test_workspace_isolation_videos(app_client, admin, other_user):
    assert app_client.get("/videos", headers=admin).json() == []
    assert app_client.get("/videos", headers=other_user).json() == []
    assert app_client.get("/videos/00000000-0000-0000-0000-000000000000", headers=admin).status_code == 404


def test_workspace_isolation_calendar(app_client, admin, other_user):
    payload = {"platform": "instagram", "scheduled_at": "2030-01-01T10:00:00Z", "title": "Isolated"}
    created = app_client.post("/calendar/schedule", json=payload, headers=admin)
    assert created.status_code == 200
    post_id = created.json()["id"]

    assert app_client.get("/calendar/events", headers=other_user).json() == []
    assert app_client.post(f"/calendar/{post_id}/cancel", headers=other_user).status_code == 404
    assert app_client.delete(f"/calendar/{post_id}", headers=other_user).status_code == 404
