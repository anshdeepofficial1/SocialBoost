"""OAuth end-to-end: start state round-trip, callback token exchange,
encrypted storage, live-sync fallback, disconnect revocation.

Provider token exchange is monkeypatched (no network in tests); everything
around it — state binding, validation, storage encryption, account upsert —
runs against the real app.
"""

from urllib.parse import urlparse


def _with_provider_env(monkeypatch):
    monkeypatch.setenv("IG_CLIENT_ID", "ig-test-client")
    monkeypatch.setenv("IG_CLIENT_SECRET", "ig-test-secret")
    monkeypatch.setenv("YT_CLIENT_ID", "yt-test-client")
    monkeypatch.setenv("YT_CLIENT_SECRET", "yt-test-secret")


def _fake_exchange(monkeypatch, platform: str, tokens: dict):
    from app.api import social

    if platform == "instagram":

        def fake(platform_arg, code, redirect_uri):  # noqa: ARG001
            assert platform_arg == "instagram"
            return tokens

        monkeypatch.setattr(social.oauth_service, "exchange_code", fake)
    else:

        def fake(platform_arg, code, redirect_uri):  # noqa: ARG001
            assert platform_arg == "youtube"
            return tokens

        monkeypatch.setattr(social.oauth_service, "exchange_code", fake)


def _start_auth(app_client, admin, platform: str, monkeypatch):
    r = app_client.get(f"/social/oauth/{platform}/start", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "state=" in body["authorize_url"] or f"state={body['state']}" in body["authorize_url"]
    assert body["state"]
    return body["state"], body["authorize_url"]


def test_start_builds_authorize_url_with_state(app_client, admin, monkeypatch):
    _with_provider_env(monkeypatch)
    state, authorize_url = _start_auth(app_client, admin, "youtube", monkeypatch)
    assert "accounts.google.com/o/oauth2/v2/auth" in authorize_url
    assert "access_type=offline" in authorize_url
    assert f"state={state}" in authorize_url

    state2, authorize2 = _start_auth(app_client, admin, "instagram", monkeypatch)
    assert "facebook.com" in authorize2
    assert state2 != state


def test_start_still_400_without_credentials(app_client, admin, monkeypatch):
    monkeypatch.delenv("YT_CLIENT_ID", raising=False)
    r = app_client.get("/social/oauth/youtube/start", headers=admin)
    assert r.status_code == 400
    assert "OAuth is not configured" in r.json()["detail"]


def test_callback_requires_valid_state(app_client, admin, monkeypatch):
    _with_provider_env(monkeypatch)
    r = app_client.get(
        "/social/oauth/instagram/callback",
        params={"code": "any", "state": "forged-state-never-issued"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "state_failed" in urlparse(r.headers["location"]).query


def test_callback_exchanges_tokens_and_connects(app_client, admin, monkeypatch):
    _with_provider_env(monkeypatch)
    _fake_exchange(
        monkeypatch,
        "youtube",
        {"access_token": "YT-AT-SECRET", "refresh_token": "YT-RT", "expires_at": "2099-01-01T00:00:00"},
    )

    monkeypatch.setattr(
        "app.api.social.oauth_service.fetch_identity",
        lambda platform, access_token: {
            "handle": "SignalStudio",
            "display_name": "Signal Studio",
            "external_id": "UC-test",
            "followers": 4200,
            "total_views": 900000,
        },
    )

    state, _ = _start_auth(app_client, admin, "youtube", monkeypatch)
    r = app_client.get(
        "/social/oauth/youtube/callback",
        params={"code": "real-code", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    location = r.headers["location"]
    assert "connected=youtube" in location
    assert "oauth_error" not in location

    accounts = [a for a in app_client.get("/social/accounts", headers=admin).json() if a["platform"] == "youtube"]
    assert len(accounts) == 1
    acc = accounts[0]
    assert acc["mode"] == "oauth"
    assert acc["handle"] == "SignalStudio"
    assert acc["followers"] == 4200, "live identity followers must be stored on connect"
    assert "credential_ref" not in acc, "the vault reference must not be exposed by the API"

    # Raw tokens must never leak through the API.
    dumped = str(acc)
    assert "YT-AT-SECRET" not in dumped

    # One-time state: reuse must fail.
    r2 = app_client.get(
        "/social/oauth/youtube/callback",
        params={"code": "real-code", "state": state},
        follow_redirects=False,
    )
    assert r2.status_code == 302
    assert "state_failed" in urlparse(r2.headers["location"]).query


def test_stored_tokens_are_encrypted_at_rest(app_client, admin, monkeypatch):
    _with_provider_env(monkeypatch)
    _fake_exchange(
        monkeypatch,
        "instagram",
        {"access_token": "IG-AT-SECRET", "expires_at": "2099-01-01T00:00:00"},
    )
    monkeypatch.setattr(
        "app.api.social.oauth_service.fetch_identity",
        lambda platform, access_token: {"handle": "7", "display_name": "n", "external_id": "7", "followers": 0},
    )
    state, _ = _start_auth(app_client, admin, "instagram", monkeypatch)
    r = app_client.get(
        "/social/oauth/instagram/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert "connected=instagram" in r.headers["location"]

    from app.db.session import SessionLocal
    from app.models.social import OAuthCredential

    with SessionLocal() as db:
        rows = db.query(OAuthCredential).filter(OAuthCredential.platform == "instagram").all()
        assert rows
        payload = rows[-1].payload
    assert "IG-AT-SECRET" not in payload, "tokens must be encrypted at rest"


def test_sync_falls_back_to_history_when_platform_unavailable(app_client, admin, monkeypatch):
    _with_provider_env(monkeypatch)
    accounts = app_client.get("/social/accounts", headers=admin).json()
    oauth_accounts = [a for a in accounts if a["mode"] == "oauth"]
    assert oauth_accounts
    acc = oauth_accounts[0]

    monkeypatch.setattr(
        "app.api.social.oauth_service.fetch_live_stats",
        lambda platform, tokens: None,  # platform unreachable
    )
    r = app_client.post(f"/social/accounts/{acc['id']}/sync", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["sync_source"] == "imported history"
    assert body["evidence"]


def test_disconnect_revokes_oauth_credential(app_client, admin):
    accounts = app_client.get("/social/accounts", headers=admin).json()
    oauth_accounts = [a for a in accounts if a["mode"] == "oauth"]
    assert oauth_accounts
    acc = oauth_accounts[0]

    r = app_client.delete(f"/social/accounts/{acc['id']}", headers=admin)
    assert r.status_code == 200 and r.json()["disconnected"] is True

    remaining = app_client.get("/social/accounts", headers=admin).json()
    assert all(a["handle"] != acc["handle"] for a in remaining if a["platform"] == acc["platform"])
