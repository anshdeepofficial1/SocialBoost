import os
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import get_current_user

router = APIRouter(prefix="/youtube", tags=["youtube"])

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_TIMEOUT = 12.0


def _api_get(resource: str, params: dict) -> dict:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="YouTube Data API is not configured. Add YOUTUBE_API_KEY to the backend environment.",
        )

    try:
        response = httpx.get(
            f"{YOUTUBE_API}/{resource}",
            params={**params, "key": key},
            timeout=_TIMEOUT,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach the YouTube Data API.") from None

    if not response.is_success:
        try:
            upstream_message = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            upstream_message = ""
        message = upstream_message or "YouTube Data API request failed."
        if response.status_code == 403 and ("quota" in message.lower() or "limit" in message.lower()):
            raise HTTPException(status_code=429, detail="YouTube API quota limit reached. Try again later.") from None
        if response.status_code == 403:
            raise HTTPException(status_code=502, detail="YouTube API denied the request. Check the server API key and API restrictions.") from None
        raise HTTPException(status_code=502, detail=message[:240]) from None

    return response.json()


def _lookup_param(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Enter a YouTube channel handle, channel URL, or channel ID.")
    if len(value) > 250:
        raise HTTPException(status_code=400, detail="Channel lookup is too long.")

    lower = value.lower()
    if "youtube.com" in lower or "youtu.be" in lower:
        candidate = value if "://" in value else f"https://{value}"
        parsed = urlparse(candidate)
        path = parsed.path.strip("/")
        segments = path.split("/") if path else []
        if len(segments) >= 2 and segments[0].lower() == "channel":
            channel_id = segments[1]
            if _CHANNEL_ID.fullmatch(channel_id):
                return "id", channel_id
            raise HTTPException(status_code=400, detail="That channel URL does not contain a valid channel ID.")
        if segments and segments[0].startswith("@"):
            handle = segments[0][1:]
            if handle and not any(ch.isspace() for ch in handle):
                return "forHandle", f"@{handle}"
        if len(segments) >= 2 and segments[0].lower() == "user":
            username = segments[1]
            if username and not any(ch.isspace() for ch in username):
                return "forUsername", username
        raise HTTPException(status_code=400, detail="Use a channel URL such as youtube.com/@handle or youtube.com/channel/UC…")

    if _CHANNEL_ID.fullmatch(value):
        return "id", value

    handle = value[1:] if value.startswith("@") else value
    if not handle or any(ch.isspace() for ch in handle) or "/" in handle:
        raise HTTPException(status_code=400, detail="Enter a channel handle (for example, @YouTube) or a channel URL.")
    return "forHandle", f"@{handle}"


def _integer(value, *, hidden: bool = False):
    if hidden or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.get("/dashboard")
def dashboard(
    channel: str = Query(..., min_length=1, max_length=250),
    limit: int = Query(10, ge=1, le=20),
    user=Depends(get_current_user),
):
    """Look up public YouTube channel statistics and its most recent public videos."""
    lookup_key, lookup_value = _lookup_param(channel)
    channels_payload = _api_get(
        "channels",
        {
            "part": "snippet,statistics,contentDetails",
            lookup_key: lookup_value,
        },
    )
    items = channels_payload.get("items") or []
    if not items:
        raise HTTPException(status_code=404, detail="No YouTube channel matched that handle or URL.")

    item = items[0]
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    content = item.get("contentDetails") or {}
    thumbnails = snippet.get("thumbnails") or {}
    thumbnail = (
        thumbnails.get("high")
        or thumbnails.get("medium")
        or thumbnails.get("default")
        or {}
    )
    channel_id = item.get("id", "")
    uploads_playlist = (content.get("relatedPlaylists") or {}).get("uploads")

    videos = []
    if uploads_playlist:
        playlist_payload = _api_get(
            "playlistItems",
            {
                "part": "contentDetails",
                "playlistId": uploads_playlist,
                "maxResults": str(limit),
            },
        )
        video_ids = [
            entry.get("contentDetails", {}).get("videoId")
            for entry in playlist_payload.get("items", [])
            if entry.get("contentDetails", {}).get("videoId")
        ]
        if video_ids:
            video_payload = _api_get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(video_ids[:50]),
                },
            )
            video_by_id = {
                video.get("id"): video
                for video in video_payload.get("items", [])
                if video.get("id")
            }
            for video_id in video_ids:
                video = video_by_id.get(video_id)
                if not video:
                    continue
                video_snippet = video.get("snippet") or {}
                video_stats = video.get("statistics") or {}
                video_content = video.get("contentDetails") or {}
                video_thumbnails = video_snippet.get("thumbnails") or {}
                video_thumb = (
                    video_thumbnails.get("high")
                    or video_thumbnails.get("medium")
                    or video_thumbnails.get("default")
                    or {}
                )
                videos.append({
                    "id": video_id,
                    "title": video_snippet.get("title") or "Untitled video",
                    "description": video_snippet.get("description") or "",
                    "thumbnail": video_thumb.get("url"),
                    "published_at": video_snippet.get("publishedAt"),
                    "views": _integer(video_stats.get("viewCount")) or 0,
                    "likes": _integer(video_stats.get("likeCount")),
                    "comments": _integer(video_stats.get("commentCount")),
                    "duration": video_content.get("duration") or "",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                })

    custom_url = snippet.get("customUrl") or ""
    handle = custom_url if custom_url.startswith("@") else (f"@{custom_url}" if custom_url else "")
    return {
        "channel": {
            "id": channel_id,
            "title": snippet.get("title") or "YouTube channel",
            "handle": handle,
            "description": snippet.get("description") or "",
            "thumbnail": thumbnail.get("url"),
            "subscribers": _integer(
                statistics.get("subscriberCount"),
                hidden=bool(statistics.get("hiddenSubscriberCount")),
            ),
            "total_views": _integer(statistics.get("viewCount")) or 0,
            "video_count": _integer(statistics.get("videoCount")) or 0,
            "published_at": snippet.get("publishedAt"),
            "url": f"https://www.youtube.com/channel/{channel_id}",
        },
        "videos": videos,
        "source": "YouTube Data API v3",
    }
