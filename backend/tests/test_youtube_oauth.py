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


def test_youtube_average_views_uses_latest_uploaded_video_stats(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    calls = []

    def fake_get(url, params, headers, timeout):  # noqa: ARG001
        calls.append((url, params))
        if url.endswith("/playlistItems"):
            return Response({
                "items": [
                    {"contentDetails": {"videoId": "video-a"}},
                    {"contentDetails": {"videoId": "video-b"}},
                    {"contentDetails": {"videoId": "video-c"}},
                ]
            })
        if url.endswith("/videos"):
            return Response({
                "items": [
                    {"statistics": {"viewCount": "100"}},
                    {"statistics": {"viewCount": "200"}},
                    {"statistics": {"viewCount": "300"}},
                ]
            })
        raise AssertionError(f"Unexpected YouTube API URL: {url}")

    monkeypatch.setattr(oauth_service.httpx, "get", fake_get)

    result = oauth_service._youtube_recent_video_metrics("token", "uploads-playlist")

    assert result == {"avg_views": 200, "avg_views_sample_size": 3}
    assert len(calls) == 2
    assert calls[0][1]["maxResults"] == 25
    assert calls[1][1]["id"] == "video-a,video-b,video-c"


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


def test_load_fresh_youtube_tokens_refreshes_and_persists_expired_access_token(monkeypatch):
    from uuid import uuid4

    from app.db.session import SessionLocal

    workspace_id = f"youtube-refresh-test-{uuid4()}"
    with SessionLocal() as db:
        oauth_service.store_tokens(
            db,
            workspace_id,
            "youtube",
            {
                "access_token": "expired-access",
                "refresh_token": "long-lived-refresh",
                "expires_at": "2000-01-01T00:00:00",
            },
        )

        def fake_refresh(tokens):
            assert tokens["refresh_token"] == "long-lived-refresh"
            return {
                **tokens,
                "access_token": "refreshed-access",
                "expires_at": "2099-01-01T00:00:00",
            }

        monkeypatch.setattr(oauth_service, "refresh_youtube", fake_refresh)
        refreshed = oauth_service.load_fresh_youtube_tokens(db, workspace_id)
        saved = oauth_service.load_tokens(db, workspace_id, "youtube")

    assert refreshed is not None
    assert refreshed["access_token"] == "refreshed-access"
    assert saved is not None
    assert saved["access_token"] == "refreshed-access"
    assert saved["refresh_token"] == "long-lived-refresh"
