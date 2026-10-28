import os
import re
from collections import Counter
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..services import oauth_service
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/youtube", tags=["youtube"])

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_TIMEOUT = 12.0


def _api_get(resource: str, params: dict, token: str = "", *, prefer_api_key: bool = True) -> dict:
    """Call the YouTube Data API.

    Priority: a configured server ``YOUTUBE_API_KEY`` reads any public channel;
    without a key, an OAuth token from the workspace's connected YouTube
    account authorises the read instead.
    """
    configured_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    # Public channel lookups should use the API key alone. Sending a stale
    # OAuth bearer token alongside a valid API key can make Google reject the
    # request as unauthenticated. The private "mine=true" path must use OAuth.
    key = configured_key if prefer_api_key else ""
    headers = {} if key else ({"Authorization": f"Bearer {token}"} if token else {})
    if not key and not token:
        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube Data API is not configured on the server. Add YOUTUBE_API_KEY to the "
                "backend environment, or connect a YouTube account (OAuth) for channel reads."
            ),
        )
    final_params = {**params, **({"key": key} if key else {})}

    try:
        response = httpx.get(
            f"{YOUTUBE_API}/{resource}",
            params=final_params,
            headers=headers,
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
        lowered = message.lower()
        auth_error = response.status_code in (400, 401, 403) and any(
            marker in lowered
            for marker in (
                "invalid authentication credentials",
                "invalidcredentials",
                "invalid credentials",
                "unauthenticated",
                "api key not valid",
                "invalid api key",
            )
        )
        if auth_error and key:
            raise HTTPException(
                status_code=502,
                detail="YouTube Data API rejected YOUTUBE_API_KEY. Check the key in the backend environment, enable YouTube Data API v3 in its Google Cloud project, and review API restrictions.",
            ) from None
        if auth_error:
            raise HTTPException(
                status_code=502,
                detail="Google rejected the connected YouTube access token. The token may have expired or been revoked. Reconnect YouTube in Integrations, or configure YOUTUBE_API_KEY on the backend for public channel lookups.",
            ) from None
        if response.status_code == 403 and ("quota" in lowered or "limit" in lowered):
            raise HTTPException(status_code=429, detail="YouTube API quota limit reached. Try again later.") from None
        if response.status_code == 403:
            raise HTTPException(status_code=502, detail="YouTube API denied the request. Check the server API key, API restrictions, and quota.") from None
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
    channel: str = Query("", max_length=250),
    limit: int = Query(10, ge=1, le=20),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Look up public YouTube channel statistics and its most recent public videos.

    With a channel argument, any public channel is read. Without one (or when
    the server has no API key), the workspace's connected YouTube account is
    used instead.
    """
    token = ""
    lookup_key, lookup_value = "", ""
    workspace_id = get_workspace_id(user, db)
    has_public_lookup = bool((channel or "").strip())
    has_api_key = bool(os.getenv("YOUTUBE_API_KEY", "").strip())
    if has_public_lookup:
        lookup_key, lookup_value = _lookup_param(channel)
        # When a server API key is configured, do not even load OAuth here:
        # public-channel reads do not require a user credential.
        if not has_api_key:
            tokens = oauth_service.load_fresh_youtube_tokens(db, workspace_id)
            token = (tokens or {}).get("access_token", "")
    else:
        # "mine=true" is an OAuth-only endpoint, even when an API key exists.
        tokens = oauth_service.load_fresh_youtube_tokens(db, workspace_id)
        token = (tokens or {}).get("access_token", "")
        if token:
            lookup_key, lookup_value = "mine", "true"
    if not lookup_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Enter a YouTube channel handle, channel URL, or channel ID. Without a server "
                "YOUTUBE_API_KEY, leaving the field blank reads your connected YouTube account."
            ),
        )
    def request(resource: str, params: dict) -> dict:
        nonlocal token
        use_api_key = lookup_key != "mine" and bool(os.getenv("YOUTUBE_API_KEY", "").strip())
        try:
            return _api_get(
                resource,
                params,
                token=token,
                prefer_api_key=lookup_key != "mine",
            )
        except HTTPException as exc:
            # A token can be revoked or expire earlier than its locally saved
            # timestamp suggests. Force one refresh-and-retry before surfacing
            # an authentication error, then persist the new encrypted grant.
            if (
                exc.status_code != 502
                or use_api_key
                or not token
                or "Google rejected the connected YouTube access token" not in str(exc.detail)
            ):
                raise
            current_tokens = oauth_service.load_tokens(db, workspace_id, "youtube") or {}
            refreshed = oauth_service.refresh_youtube(current_tokens)
            if not refreshed or not refreshed.get("access_token"):
                raise
            oauth_service.store_tokens(db, workspace_id, "youtube", refreshed)
            token = refreshed["access_token"]
            return _api_get(
                resource,
                params,
                token=token,
                prefer_api_key=lookup_key != "mine",
            )

    channels_payload = request(
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
        playlist_payload = request(
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
            video_payload = request(
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
                    "views": _integer(video_stats.get("viewCount"),),
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
            "total_views": _integer(statistics.get("viewCount")),
            "video_count": _integer(statistics.get("videoCount")),
            "published_at": snippet.get("publishedAt"),
            "url": f"https://www.youtube.com/channel/{channel_id}",
        },
        "videos": videos,
        "source": "YouTube Data API v3",
    }

@router.get("/competitors")
def competitors(
    limit: int = Query(6, ge=1, le=10),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suggest public competitor channels based on the connected channel's niche.

    The connected channel and its recent upload titles seed a small topic query.
    Public statistics are fetched from YouTube, and the user's own channel is
    excluded. Suggestions are candidates to study, not claims that a channel's
    success is caused by any one factor.
    """
    workspace_id = get_workspace_id(user, db)
    tokens = oauth_service.load_fresh_youtube_tokens(db, workspace_id) or {}
    access_token = tokens.get("access_token", "")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Connect YouTube in Accounts first so SocialBoost can learn the channel niche and recommend comparable channels.",
        )

    own_payload = _api_get(
        "channels",
        {"part": "snippet,statistics,contentDetails", "mine": "true"},
        token=access_token,
        prefer_api_key=False,
    )
    own_items = own_payload.get("items") or []
    if not own_items:
        raise HTTPException(status_code=404, detail="The connected Google account has no accessible YouTube channel.")
    own = own_items[0]
    own_id = own.get("id", "")
    own_snippet = own.get("snippet") or {}
    own_title = own_snippet.get("title") or "YouTube channel"
    uploads_id = (
        (own.get("contentDetails") or {}).get("relatedPlaylists") or {}
    ).get("uploads", "")

    recent_uploads = oauth_service._youtube_recent_videos(access_token, uploads_id, max_results=12)
    known_titles = []
    for upload in recent_uploads:
        title = str(upload.get("title") or "").strip()
        if title:
            known_titles.append(title)
    if not known_titles:
        known_titles = [own_title]

    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "your", "you", "are", "was",
        "how", "why", "what", "when", "where", "short", "shorts", "video", "official",
        "new", "latest", "full", "part", "episode", "status", "reels", "youtube", "instagram",
        "for", "song", "music", "hd", "4k",
    }
    terms = Counter(
        token.lower()
        for text_value in [own_title, *known_titles]
        for token in re.findall(r"[^\W_]{3,}", text_value, flags=re.UNICODE)
        if token.lower() not in stop_words and not token.isdigit()
    )
    topics = [word for word, _ in terms.most_common(3)]
    query = " ".join(topics) or own_title
    if not query.strip():
        query = own_title

    search_payload = _api_get(
        "search",
        {"part": "snippet", "type": "channel", "maxResults": min(25, max(12, limit * 3)), "q": query},
        token=access_token,
        prefer_api_key=True,
    )
    candidate_ids = []
    initial = {}
    for item in search_payload.get("items") or []:
        identifier = ((item.get("id") or {}).get("channelId") or "").strip()
        if not identifier or identifier == own_id:
            continue
        candidate_ids.append(identifier)
        initial[identifier] = item.get("snippet") or {}
    candidate_ids = list(dict.fromkeys(candidate_ids))[: max(limit * 2, limit)]
    if not candidate_ids:
        return {"source": "YouTube Data API v3", "query": query, "topics": topics, "competitors": []}

    channels_payload = _api_get(
        "channels",
        {"part": "snippet,statistics,contentDetails", "id": ",".join(candidate_ids[:50])},
        token=access_token,
        prefer_api_key=True,
    )
    candidates = []
    for channel in channels_payload.get("items") or []:
        channel_id = channel.get("id", "")
        if not channel_id or channel_id == own_id:
            continue
        snippet = channel.get("snippet") or initial.get(channel_id) or {}
        stats = channel.get("statistics") or {}
        content = channel.get("contentDetails") or {}
        channel_uploads = (content.get("relatedPlaylists") or {}).get("uploads", "")
        public_videos = oauth_service._youtube_recent_videos(access_token, channel_uploads, max_results=3)
        snippet_text = f"{snippet.get('title', '')} {snippet.get('description', '')}".lower()
        matched_topics = [topic for topic in topics if topic.lower() in snippet_text]
        candidates.append({
            "id": channel_id,
            "title": snippet.get("title") or "YouTube channel",
            "handle": snippet.get("customUrl") or "",
            "description": snippet.get("description") or "",
            "thumbnail": (
                (snippet.get("thumbnails") or {}).get("high")
                or (snippet.get("thumbnails") or {}).get("medium")
                or (snippet.get("thumbnails") or {}).get("default")
                or {}
            ).get("url"),
            "subscribers": _integer(
                stats.get("subscriberCount"),
                hidden=bool(stats.get("hiddenSubscriberCount")),
            ),
            "total_views": _integer(stats.get("viewCount")),
            "video_count": _integer(stats.get("videoCount")),
            "url": f"https://www.youtube.com/channel/{channel_id}",
            "matched_topics": matched_topics or topics[:2],
            "recent_videos": [
                {
                    "id": video.get("post_id"),
                    "title": video.get("title") or "Untitled video",
                    "published_at": video.get("published_at"),
                    "views": video.get("views"),
                    "url": video.get("permalink"),
                }
                for video in public_videos
            ],
        })

    candidates.sort(
        key=lambda item: (
            len(item["matched_topics"]),
            item["subscribers"] or 0,
            item["total_views"] or 0,
        ),
        reverse=True,
    )
    return {
        "source": "YouTube Data API v3",
        "channel": {"id": own_id, "title": own_title},
        "query": query,
        "topics": topics,
        "competitors": candidates[:limit],
        "note": "Channels are matched from recent upload topics and public stats. Compare their formats and upload patterns; correlation does not prove a cause of growth.",
    }

