"""Regression tests for YouTube Data API authentication selection."""

import pytest
from fastapi import HTTPException

from app.api import youtube as youtube_api


class FakeResponse:
    def __init__(self, *, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self.payload


def test_public_lookup_uses_api_key_without_stale_oauth_header(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "server-api-key")
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload={"items": []})

    monkeypatch.setattr(youtube_api.httpx, "get", fake_get)

    result = youtube_api._api_get("channels", {"part": "snippet"}, token="stale-oauth-token")

    assert result == {"items": []}
    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["params"]["key"] == "server-api-key"
    assert kwargs["headers"] == {}
    assert "Authorization" not in kwargs["headers"]


def test_oauth_fallback_uses_bearer_when_server_key_is_missing(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload={"items": []})

    monkeypatch.setattr(youtube_api.httpx, "get", fake_get)

    result = youtube_api._api_get("channels", {"part": "snippet"}, token="valid-oauth-token")

    assert result == {"items": []}
    _, kwargs = calls[0]
    assert "key" not in kwargs["params"]
    assert kwargs["headers"]["Authorization"] == "Bearer valid-oauth-token"


def test_expired_oauth_error_is_reported_with_a_recovery_step(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    def fake_get(url, **kwargs):
        return FakeResponse(
            status_code=401,
            payload={
                "error": {
                    "message": "Request had invalid authentication credentials. Expected OAuth 2 access token."
                }
            },
        )

    monkeypatch.setattr(youtube_api.httpx, "get", fake_get)

    with pytest.raises(HTTPException) as exc:
        youtube_api._api_get("channels", {"part": "snippet"}, token="expired-token")

    assert exc.value.status_code == 502
    assert "Reconnect YouTube in Integrations" in exc.value.detail
    assert "YOUTUBE_API_KEY" in exc.value.detail
