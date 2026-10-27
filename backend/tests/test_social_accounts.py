"""Connected account flows: connect, sync, list, disconnect, providers."""


def test_providers_report_configuration(app_client, admin):
    r = app_client.get("/social/providers", headers=admin)
    assert r.status_code == 200
    by_platform = {p["platform"]: p for p in r.json()}
    assert set(by_platform) == {"instagram", "youtube"}
    for p in by_platform.values():
        assert p["mode"] in ("oauth", "sandbox")
        assert isinstance(p["required_env"], list) and p["required_env"]
        assert isinstance(p["scopes"], list) and p["scopes"]


def test_connect_requires_valid_handle(app_client, admin):
    r = app_client.post("/social/accounts", json={"platform": "instagram", "handle": "   "}, headers=admin)
    assert r.status_code == 400

    r = app_client.post("/social/accounts", json={"platform": "instagram", "handle": "not a handle"}, headers=admin)
    assert r.status_code == 400

    r = app_client.post("/social/accounts", json={"platform": "myspace", "handle": "x"}, headers=admin)
    assert r.status_code == 400


def test_oauth_connect_requires_credentials(app_client, admin):
    r = app_client.post("/social/accounts", json={"platform": "instagram", "handle": "x", "mode": "oauth"}, headers=admin)
    assert r.status_code == 400
    assert "OAuth is not configured" in r.json()["detail"]


def test_oauth_start_unavailable_without_credentials(app_client, admin):
    r = app_client.get("/social/oauth/instagram/start", headers=admin)
    assert r.status_code == 400


def test_connect_normalises_handles(app_client, admin):
    r = app_client.post(
        "/social/accounts",
        json={"platform": "instagram", "handle": "@Signal.Studio", "display_name": "Signal Studio"},
        headers=admin,
    )
    assert r.status_code == 200
    acc = r.json()
    assert acc["handle"] == "Signal.Studio"
    assert acc["platform"] == "instagram"
    assert acc["mode"] == "sandbox"
    assert acc["status"] == "connected"
    assert acc["scopes"]

    # Connecting again updates rather than duplicating.
    again = app_client.post(
        "/social/accounts",
        json={"platform": "instagram", "handle": "signal.studio"},
        headers=admin,
    )
    assert again.status_code == 200
    accounts = app_client.get("/social/accounts", headers=admin).json()
    assert len([a for a in accounts if a["platform"] == "instagram"]) == 1


def test_connect_accepts_profile_urls(app_client, admin):
    r = app_client.post(
        "/social/accounts",
        json={"platform": "youtube", "handle": "https://youtube.com/@SignalStudio/"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["handle"] == "@SignalStudio"


def test_connect_then_sync_and_disconnect(app_client, admin):
    app_client.post("/social/accounts", json={"platform": "youtube", "handle": "syncme"}, headers=admin)
    accounts = app_client.get("/social/accounts", headers=admin).json()
    acc = next(a for a in accounts if a["handle"] == "syncme")

    synced = app_client.post(f"/social/accounts/{acc['id']}/sync", headers=admin)
    assert synced.status_code == 200
    assert synced.json()["last_synced_at"] is not None
    assert "evidence" in synced.json()

    removed = app_client.delete(f"/social/accounts/{acc['id']}", headers=admin)
    assert removed.status_code == 200
    assert removed.json()["disconnected"] is True

    remaining = app_client.get("/social/accounts", headers=admin).json()
    assert all(a["handle"] != "syncme" for a in remaining)


def test_sync_unknown_account_404(app_client, admin):
    r = app_client.post("/social/accounts/does-not-exist/sync", headers=admin)
    assert r.status_code == 404


def test_accounts_are_workspace_scoped(app_client, admin, other_user):
    app_client.post("/social/accounts", json={"platform": "instagram", "handle": "mine.only"}, headers=admin)
    assert all(a["handle"] != "mine.only" for a in app_client.get("/social/accounts", headers=other_user).json())


def test_summary_and_legacy_status(app_client, admin):
    # Self-contained: ensure both platforms are connected regardless of test order.
    app_client.post("/social/accounts", json={"platform": "instagram", "handle": "summary.ig"}, headers=admin)
    app_client.post("/social/accounts", json={"platform": "youtube", "handle": "summary.yt"}, headers=admin)

    summary = app_client.get("/social/summary", headers=admin)
    assert summary.status_code == 200
    assert summary.json()["connected"] == 2

    accounts = {a["platform"]: a for a in app_client.get("/social/accounts", headers=admin).json()}
    assert accounts["instagram"]["handle"] == "summary.ig"
    assert accounts["youtube"]["handle"] == "summary.yt"

    status = app_client.get("/integrations/status", headers=admin)
    assert status.status_code == 200
    body = status.json()
    # The legacy endpoint must reflect the real rows, not a hard-coded value.
    for platform in ("instagram", "youtube"):
        assert platform in accounts
        assert body[platform]["connected"] is True
        assert body[platform]["handle"] == accounts[platform]["handle"]
    assert body["live_publishing_enabled"] is False
