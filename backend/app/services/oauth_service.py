"""OAuth flows for Instagram (Meta) and YouTube (Google).

Everything provider-facing lives here so ``app/api/social.py`` stays thin:

* authorisation URL + CSRF state round-trip (``OAuthState`` rows);
* token exchange and (optional) long-lived token upgrade;
* token persistence via :class:`~app.models.social.OAuthCredential`,
  encrypted at rest with a key derived from ``SECRET_KEY`` — raw tokens are
  never returned by the API and never stored in ``social_accounts``;
* best-effort live identity/statistics reads. Read-only scopes only.

Important honesty rule carried over from the rest of this codebase: when a
platform call fails, callers fall back to imported history rather than
inventing numbers. Publishing remains a separate, not-implemented feature.
"""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.social import OAuthCredential, OAuthState

log = logging.getLogger("socialboost.oauth")

STATE_TTL_MINUTES = 15
TIMEOUT = 30.0

GRAPH_VERSION = "v26.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


# --------------------------------------------------------------------------
# Encryption helpers
# --------------------------------------------------------------------------


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(payload: dict) -> str:
    return _fernet().encrypt(json.dumps(payload).encode()).decode()


def _decrypt(blob: str) -> dict | None:
    try:
        return json.loads(_fernet().decrypt(blob.encode()).decode())
    except (InvalidToken, ValueError):
        log.warning("could not decrypt an OAuth credential payload")
        return None


# --------------------------------------------------------------------------
# CSRF state round-trip
# --------------------------------------------------------------------------


def create_state(db: Session, workspace_id: str, platform: str, redirect_uri: str) -> OAuthState:
    import secrets

    row = OAuthState(
        state=secrets.token_urlsafe(24),
        workspace_id=workspace_id,
        platform=platform,
        redirect_uri=redirect_uri,
        expires_at=datetime.utcnow() + timedelta(minutes=STATE_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def consume_state(db: Session, state: str | None, platform: str) -> dict | None:
    """Validate and delete the state row, returning its binding values.

    A plain dict is returned because the row is removed from the session —
    accessing attributes of a deleted instance re-triggers expiry.
    """
    if not state:
        return None
    row = (
        db.query(OAuthState)
        .filter(OAuthState.state == state, OAuthState.platform == platform)
        .first()
    )
    if not row or row.expires_at < datetime.utcnow():
        db.commit()
        return None
    binding = {"workspace_id": row.workspace_id, "redirect_uri": row.redirect_uri}
    db.delete(row)
    db.commit()
    return binding


# --------------------------------------------------------------------------
# Token exchange
# --------------------------------------------------------------------------


def exchange_instagram(code: str, redirect_uri: str) -> dict:
    client_id = os.getenv("IG_CLIENT_ID", "")
    client_secret = os.getenv("IG_CLIENT_SECRET", "")
    r = httpx.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    tokens = {"access_token": r.json().get("access_token", "")}

    # Upgrade to a long-lived page token when Meta allows it. Failure is not
    # fatal: the short-lived token still works for identity reads.
    try:
        r2 = httpx.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": tokens["access_token"],
            },
            timeout=TIMEOUT,
        )
        if r2.status_code == 200 and r2.json().get("access_token"):
            tokens["access_token"] = r2.json()["access_token"]
            expires = r2.json().get("expires_in")
            if expires:
                tokens["expires_at"] = (
                    datetime.utcnow() + timedelta(seconds=int(expires))
                ).isoformat()
    except Exception:
        log.info("long-lived token upgrade skipped", exc_info=True)
    return tokens


def exchange_youtube(code: str, redirect_uri: str) -> dict:
    r = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": os.getenv("YT_CLIENT_ID", ""),
            "client_secret": os.getenv("YT_CLIENT_SECRET", ""),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    tokens = {
        "access_token": body.get("access_token", ""),
        "refresh_token": body.get("refresh_token", ""),
        "expires_in": body.get("expires_in", 3600),
    }
    if tokens["access_token"]:
        tokens["expires_at"] = (
            datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
        ).isoformat()
    return tokens


def refresh_youtube(tokens: dict) -> dict | None:
    """Best-effort refresh; returns updated tokens or ``None``."""
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None
    try:
        r = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": os.getenv("YT_CLIENT_ID", ""),
                "client_secret": os.getenv("YT_CLIENT_SECRET", ""),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        updated = dict(tokens)
        updated["access_token"] = body.get("access_token", updated["access_token"])
        updated["expires_at"] = (
            datetime.utcnow() + timedelta(seconds=int(body.get("expires_in", 3600)))
        ).isoformat()
        return updated
    except Exception:
        return None


def exchange_code(platform: str, code: str, redirect_uri: str) -> dict:
    if platform == "instagram":
        return exchange_instagram(code, redirect_uri)
    return exchange_youtube(code, redirect_uri)


# --------------------------------------------------------------------------
# Credential storage
# --------------------------------------------------------------------------


def store_tokens(db: Session, workspace_id: str, platform: str, tokens: dict) -> OAuthCredential:
    row = (
        db.query(OAuthCredential)
        .filter(OAuthCredential.workspace_id == workspace_id, OAuthCredential.platform == platform)
        .first()
    )
    # Google may omit refresh_token on a subsequent authorization even when an
    # existing grant already has one. Preserve the usable long-lived token so
    # a reconnect does not accidentally downgrade the credential to one-hour
    # access-token-only mode.
    if row and platform == "youtube" and not tokens.get("refresh_token"):
        previous = _decrypt(row.payload)
        if previous and previous.get("refresh_token"):
            tokens = {**tokens, "refresh_token": previous["refresh_token"]}
    blob = _encrypt(tokens)
    expires = _parse_iso(tokens.get("expires_at"))
    if row:
        row.payload = blob
        row.status = "active"
        row.expires_at = expires
        row.updated_at = datetime.utcnow()
    else:
        row = OAuthCredential(
            workspace_id=workspace_id,
            platform=platform,
            payload=blob,
            status="active",
            expires_at=expires,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_tokens(db: Session, workspace_id: str, platform: str) -> dict | None:
    row = (
        db.query(OAuthCredential)
        .filter(OAuthCredential.workspace_id == workspace_id, OAuthCredential.platform == platform)
        .first()
    )
    if not row or row.status != "active":
        return None
    tokens = _decrypt(row.payload)
    return tokens if tokens else None


def mark_revoked(db: Session, workspace_id: str, platform: str) -> None:
    row = (
        db.query(OAuthCredential)
        .filter(OAuthCredential.workspace_id == workspace_id, OAuthCredential.platform == platform)
        .first()
    )
    if row:
        row.status = "revoked"
        db.commit()


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _token_is_fresh(tokens: dict) -> bool:
    expires = _parse_iso(tokens.get("expires_at"))
    return bool(expires and expires > datetime.utcnow() + timedelta(minutes=5))


# --------------------------------------------------------------------------
# Best-effort live reads (honest: any failure falls back to history)
# --------------------------------------------------------------------------


def _graph_get(path: str, params: dict, access_token: str) -> dict:
    """Call a versioned Graph API endpoint with a server-side access token."""
    response = httpx.get(
        f"{GRAPH_BASE}/{path.lstrip('/')}",
        params={**params, "access_token": access_token},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


class InstagramPagePermissionMissing(RuntimeError):
    """Raised when the token does not have the required Page-list permission."""


class InstagramBusinessManagementPermissionMissing(RuntimeError):
    """Raised when an empty Page list coincides with a missing business_management grant."""


class InstagramPagesNotFound(RuntimeError):
    """Raised when Meta returns no manageable Facebook Pages for the user token."""


class InstagramAccountNotFound(RuntimeError):
    """Raised when Pages are visible but none exposes a linked professional Instagram account."""


class YouTubeChannelNotFound(RuntimeError):
    """Raised when Google login succeeds but the selected account has no accessible YouTube channel."""


def _youtube_recent_video_metrics(
    access_token: str,
    uploads_playlist_id: str,
    max_results: int = 25,
) -> dict:
    """Average view counts for the latest uploaded videos, without search.list quota cost."""
    if not uploads_playlist_id:
        return {"avg_views": None, "avg_views_sample_size": 0}
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        playlist_response = httpx.get(
            f"{YOUTUBE_API}/playlistItems",
            params={
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": max(1, min(int(max_results), 50)),
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        playlist_response.raise_for_status()
        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in playlist_response.json().get("items") or []
            if item.get("contentDetails", {}).get("videoId")
        ]
        if not video_ids:
            return {"avg_views": None, "avg_views_sample_size": 0}

        videos_response = httpx.get(
            f"{YOUTUBE_API}/videos",
            params={"part": "statistics", "id": ",".join(video_ids)},
            headers=headers,
            timeout=TIMEOUT,
        )
        videos_response.raise_for_status()
        view_counts = []
        for item in videos_response.json().get("items") or []:
            value = (item.get("statistics") or {}).get("viewCount")
            if value is None:
                continue
            try:
                view_counts.append(max(0, int(value)))
            except (TypeError, ValueError):
                continue
        if not view_counts:
            return {"avg_views": None, "avg_views_sample_size": 0}
        return {
            "avg_views": int(sum(view_counts) / len(view_counts)),
            "avg_views_sample_size": len(view_counts),
        }
    except Exception:
        # Channel-level subscriber/video totals should still sync if recent
        # video statistics are temporarily unavailable.
        log.info("recent YouTube video view lookup failed", exc_info=True)
        return {"avg_views": None, "avg_views_sample_size": 0}


def fetch_identity(platform: str, access_token: str) -> dict:
    """Resolve the actual linked Instagram professional account or YouTube channel."""
    if platform == "youtube":
        r = httpx.get(
            f"{YOUTUBE_API}/channels",
            params={"part": "snippet,statistics,contentDetails", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
        if not items:
            raise YouTubeChannelNotFound(
                "Google authorization succeeded, but no YouTube channel was returned for this account."
            )
        it = items[0]
        snippet = it.get("snippet", {})
        stats = it.get("statistics", {})
        uploads_playlist_id = (
            it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
        )
        recent = _youtube_recent_video_metrics(access_token, uploads_playlist_id)
        custom = snippet.get("customUrl") or ""
        return {
            "handle": custom.lstrip("@") if custom else it.get("id", ""),
            "display_name": snippet.get("title") or "",
            "external_id": it.get("id", ""),
            "followers": int(stats.get("subscriberCount", 0) or 0),
            "post_count": int(stats.get("videoCount", 0) or 0),
            "total_views": int(stats.get("viewCount", 0) or 0),
            "avg_views": recent["avg_views"],
            "avg_views_sample_size": recent["avg_views_sample_size"],
        }

    # Meta's documented /me/accounts query uses instagram_business_account
    # as a field. Requesting an expanded nested field set here can fail the
    # entire request and was previously misreported as "no account found".
    user = _graph_get("me", {"fields": "id,name"}, access_token)
    pages = []
    cursor = None
    for _ in range(10):
        page_params = {
            "fields": "id,name,access_token,tasks,instagram_business_account",
            "limit": 100,
        }
        if cursor:
            page_params["after"] = cursor
        page_result = _graph_get("me/accounts", page_params, access_token)
        pages.extend(page_result.get("data") or [])
        cursor = (page_result.get("paging") or {}).get("cursors", {}).get("after")
        if not cursor:
            break

    if not pages:
        # A granted OAuth scope and an empty Page edge mean different things.
        # Check the actual user-token grants before showing the user a generic
        # Page-access error. Never log or return the access token itself.
        permission_result = _graph_get("me/permissions", {}, access_token)
        permission_rows = permission_result.get("data") or []
        permission_status = {
            row.get("permission"): row.get("status")
            for row in permission_rows
            if row.get("permission")
        }
        if permission_status.get("pages_show_list") != "granted":
            log.warning(
                "Instagram OAuth token lacks granted pages_show_list permission; returned statuses: %s",
                {
                    name: permission_status.get(name, "not returned")
                    for name in (
                        "pages_show_list",
                        "pages_read_engagement",
                        "instagram_basic",
                        "business_management",
                    )
                },
            )
            raise InstagramPagePermissionMissing(
                "The Facebook user token does not have a granted pages_show_list permission."
            )
        if permission_status.get("business_management") != "granted":
            log.warning(
                "Instagram OAuth token has pages_show_list but lacks business_management; "
                "Meta may be hiding Pages assigned through a Business Portfolio"
            )
            raise InstagramBusinessManagementPermissionMissing(
                "The Facebook user token does not have a granted business_management permission, "
                "which may be required to discover this Page through its Business Portfolio."
            )
        log.warning(
            "Instagram OAuth token has both pages_show_list and business_management granted "
            "but Meta returned zero Pages; check Page access and Business Portfolio assignment"
        )
        raise InstagramPagesNotFound(
            "Meta returned zero manageable Facebook Pages even though pages_show_list is granted. "
            "Check Page access and Business Portfolio assignment for this Facebook profile."
        )
    log.debug("Meta returned %s manageable Page(s) while resolving Instagram identity", len(pages))

    for page in pages:
        page_id = page.get("id")
        if not page_id:
            continue
        page_token = page.get("access_token") or ""
        instagram_ref = page.get("instagram_business_account")

        # Some Page responses omit expanded details. Ask the Page edge directly,
        # using the user token, then use its Page token for Instagram profile/media.
        if not instagram_ref:
            page_detail = _graph_get(
                page_id,
                {"fields": "id,name,access_token,instagram_business_account"},
                access_token,
            )
            instagram_ref = page_detail.get("instagram_business_account")
            page_token = page_token or page_detail.get("access_token") or ""

        if isinstance(instagram_ref, str):
            instagram_id = instagram_ref
        elif isinstance(instagram_ref, dict):
            instagram_id = instagram_ref.get("id") or ""
        else:
            instagram_id = ""
        if not instagram_id:
            continue
        if not page_token:
            raise RuntimeError(
                "Meta found the linked Instagram account but did not return its Page access token. "
                "Reconnect and ensure pages_show_list and pages_read_engagement are granted."
            )

        profile = _graph_get(
            instagram_id,
            {"fields": "id,username,name,followers_count,media_count,profile_picture_url"},
            page_token,
        )
        username = profile.get("username") or (
            instagram_ref.get("username", "") if isinstance(instagram_ref, dict) else ""
        )
        if not username:
            continue
        return {
            "handle": username,
            "display_name": profile.get("name") or username,
            "external_id": profile.get("id") or instagram_id,
            "followers": int(profile.get("followers_count", 0) or 0),
            "post_count": int(profile.get("media_count", 0) or 0),
            "profile_picture_url": profile.get("profile_picture_url") or "",
            "page_id": page_id,
            "page_name": page.get("name") or "",
            "page_access_token": page_token,
            "instagram_user_id": profile.get("id") or instagram_id,
            "facebook_user_id": user.get("id") or "",
        }

    raise InstagramAccountNotFound(
        "Meta successfully listed the managed Pages, but none exposed a linked Instagram professional account. "
        "Check the Instagram-to-Page link and verify the selected Page is the one connected to that account."
    )


def _metric_value(payload: dict, metric_name: str) -> int | None:
    for metric in payload.get("data") or []:
        if metric.get("name") != metric_name:
            continue
        if isinstance(metric.get("total_value"), dict):
            value = metric["total_value"].get("value")
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        values = metric.get("values") or []
        if values:
            value = values[-1].get("value")
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
    return None


def fetch_live_stats(platform: str, tokens: dict) -> dict | None:
    """Fetch live provider metrics without substituting Facebook Page counters for Instagram."""
    try:
        if platform == "youtube":
            access = tokens.get("access_token", "")
            if not _token_is_fresh(tokens):
                refreshed = refresh_youtube(tokens)
                if refreshed:
                    access = refreshed["access_token"]
                    tokens.update(refreshed)
            if not access:
                return None
            r = httpx.get(
                f"{YOUTUBE_API}/channels",
                params={"part": "statistics,contentDetails", "mine": "true"},
                headers={"Authorization": f"Bearer {access}"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items") or []
            if not items:
                return None
            channel = items[0]
            stats = channel.get("statistics", {})
            uploads_playlist_id = (
                channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
            )
            recent = _youtube_recent_video_metrics(access, uploads_playlist_id)
            return {
                "followers": int(stats.get("subscriberCount", 0) or 0),
                "post_count": int(stats.get("videoCount", 0) or 0),
                "total_views": int(stats.get("viewCount", 0) or 0),
                "avg_views": recent["avg_views"],
                "avg_views_sample_size": recent["avg_views_sample_size"],
                "refreshed_password_grant": bool(tokens.get("refresh_token")),
            }

        if platform != "instagram":
            return None

        instagram_id = tokens.get("instagram_user_id")
        page_token = tokens.get("page_access_token")
        identity = None
        # Older saved credentials may only contain the Facebook user token.
        # Resolve the attached IG account on first sync so a new login is not
        # required solely to refresh the token payload.
        if not instagram_id or not page_token:
            identity = fetch_identity("instagram", tokens.get("access_token", ""))
            instagram_id = identity["instagram_user_id"]
            page_token = identity["page_access_token"]
            tokens.update({
                "instagram_user_id": instagram_id,
                "page_access_token": page_token,
                "page_id": identity.get("page_id", ""),
                "instagram_handle": identity.get("handle", ""),
                "instagram_display_name": identity.get("display_name", ""),
                "instagram_profile_picture_url": identity.get("profile_picture_url", ""),
            })

        profile = _graph_get(
            instagram_id,
            {"fields": "id,username,name,followers_count,media_count,profile_picture_url"},
            page_token,
        )
        identity = identity or {}
        identity.update({
            "handle": profile.get("username") or identity.get("handle") or tokens.get("instagram_handle") or "",
            "display_name": profile.get("name") or identity.get("display_name") or tokens.get("instagram_display_name") or "",
            "external_id": profile.get("id") or instagram_id,
            "followers": int(profile.get("followers_count", 0) or 0),
            "post_count": int(profile.get("media_count", 0) or 0),
            "profile_picture_url": profile.get("profile_picture_url") or identity.get("profile_picture_url") or "",
        })
        tokens.update({
            "instagram_user_id": identity["external_id"],
            "instagram_handle": identity["handle"],
            "instagram_display_name": identity["display_name"],
            "instagram_profile_picture_url": identity["profile_picture_url"],
        })

        media_response = _graph_get(
            f"{identity['external_id']}/media",
            {
                "fields": "id,caption,media_type,media_product_type,timestamp,like_count,comments_count,permalink",
                "limit": 25,
            },
            page_token,
        )
        media_rows = []
        total_views = total_likes = total_comments = total_reach = 0
        available_view_metrics = 0
        for item in media_response.get("data") or []:
            media_type = (item.get("media_product_type") or item.get("media_type") or "").upper()
            is_video = media_type in {"REELS", "VIDEO", "STORY"}
            metric_names = (
                "views,reach,likes,comments,saved,shares,total_interactions"
                if is_video
                else "reach,likes,comments,saved,shares,total_interactions"
            )
            insight_data = {}
            try:
                insight_data = _graph_get(
                    f"{item['id']}/insights",
                    {"metric": metric_names},
                    page_token,
                )
            except Exception:
                # A single unsupported metric/media type must not discard the
                # rest of the account's live media data.
                try:
                    fallback_names = "plays,reach,saved,shares,total_interactions" if is_video else "reach,saved,shares,total_interactions"
                    insight_data = _graph_get(
                        f"{item['id']}/insights",
                        {"metric": fallback_names},
                        page_token,
                    )
                except Exception:
                    insight_data = {}

            views = _metric_value(insight_data, "views")
            if views is None:
                views = _metric_value(insight_data, "plays")
            reach = _metric_value(insight_data, "reach")
            likes = int(item.get("like_count", 0) or 0)
            comments = int(item.get("comments_count", 0) or 0)
            saves = _metric_value(insight_data, "saved")
            shares = _metric_value(insight_data, "shares")
            total_interactions = _metric_value(insight_data, "total_interactions")
            if views is not None:
                total_views += views
                available_view_metrics += 1
            if reach is not None:
                total_reach += reach
            total_likes += likes
            total_comments += comments

            timestamp = item.get("timestamp") or ""
            published_at = None
            if timestamp:
                try:
                    published_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).replace(tzinfo=None).isoformat()
                except ValueError:
                    published_at = None
            media_rows.append({
                "post_id": item.get("id", ""),
                "published_at": published_at,
                "content_type": "reel" if media_type == "REELS" else ("video" if media_type == "VIDEO" else "post"),
                "title": (item.get("caption") or "")[:240],
                "caption": item.get("caption") or "",
                "permalink": item.get("permalink") or "",
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "reach": reach,
                "total_interactions": total_interactions,
            })

        media_views = [row["views"] for row in media_rows if row["views"] is not None]
        total_known_views = sum(media_views)
        avg_views = int(total_known_views / len(media_views)) if media_views else 0
        known_view_ids = {row["post_id"] for row in media_rows if row["views"] is not None}
        engagements = sum(
            row["likes"] + row["comments"]
            for row in media_rows
            if row["post_id"] in known_view_ids
        )
        engagement_rate = round(engagements / total_known_views, 4) if total_known_views else 0.0
        return {
            **identity,
            "followers": int(profile.get("followers_count", 0) or 0),
            "post_count": int(profile.get("media_count", 0) or 0),
            "avg_views": avg_views,
            "total_views": total_known_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_reach": total_reach,
            "engagement_rate": engagement_rate,
            "media": media_rows,
            "view_metrics_available": available_view_metrics,
            "data_source": "Instagram Graph API",
        }
    except Exception as exc:
        # Keep a safe diagnostic category for the sync endpoint/UI. Never expose
        # provider response bodies, URLs, or credentials to the browser.
        tokens["_sync_error_type"] = type(exc).__name__
        log.warning(
            "live stats fetch failed for %s (error_type=%s)",
            platform,
            type(exc).__name__,
            exc_info=True,
        )
        return None
