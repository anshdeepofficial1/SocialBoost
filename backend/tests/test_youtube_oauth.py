"""Regression coverage for YouTube OAuth identity and long-lived credentials."""

from app.services import oauth_service


def test_youtube_identity_reports_missing_channel_separately(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        @staticmethod
        def json():
            return {"items": []}

    monkeypatch.setattr(oauth_service.httpx, "get", lambda *args, **kwargs: Response())

    try:
        oauth_service.fetch_identity("youtube", "not-a-real-token")
    except oauth_service.YouTubeChannelNotFound:
        pass
    else:
        raise AssertionError("An account without a YouTube channel should get a specific error")


def test_reconnecting_youtube_preserves_existing_refresh_token(app_client):
    from uuid import uuid4

    from app.db.session import SessionLocal

    workspace_id = f"youtube-oauth-test-{uuid4()}"
    with SessionLocal() as db:
        oauth_service.store_tokens(
            db,
            workspace_id,
            "youtube",
            {
                "access_token": "old-access",
                "refresh_token": "long-lived-refresh",
                "expires_at": "2099-01-01T00:00:00",
            },
        )
        oauth_service.store_tokens(
            db,
            workspace_id,
            "youtube",
            {
                "access_token": "new-access",
                "expires_at": "2099-01-01T00:00:00",
            },
        )
        saved = oauth_service.load_tokens(db, workspace_id, "youtube")

    assert saved is not None
    assert saved["access_token"] == "new-access"
    assert saved["refresh_token"] == "long-lived-refresh"
