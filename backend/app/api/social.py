import os
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import null
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..models.social import SocialAccount
from ..services import oauth_service
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/social", tags=["social"])

PLATFORMS = {
    "instagram": {
        "label": "Instagram",
        "product": "Reels",
        "auth_url": "https://www.facebook.com/v26.0/dialog/oauth",
        # business_management can be necessary for /me/accounts to return
        # Pages that are assets of a Business Portfolio. Without it, Meta may
        # return data=[] even while pages_show_list is granted.
        "scope": "instagram_basic,instagram_manage_insights,instagram_content_publish,pages_show_list,pages_read_engagement,business_management",
        "client_id_env": "IG_CLIENT_ID",
        "client_secret_env": "IG_CLIENT_SECRET",
    },
    "youtube": {
        "label": "YouTube",
        "product": "Shorts",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scope": "https://www.googleapis.com/auth/youtube.readonly",
        "client_id_env": "YT_CLIENT_ID",
        "client_secret_env": "YT_CLIENT_SECRET",
    },
}


class ConnectIn(BaseModel):
    platform: str
    handle: str
    display_name: str = ""
    mode: str = "sandbox"


def _norm_handle(platform: str, handle: str) -> str:
    h = handle.strip()
    if not h:
        raise HTTPException(400, "Enter the account handle you want to connect.")
    h = h.lstrip("@")
    if platform == "youtube" and "youtube.com/" in h:
        h = h.rstrip("/").split("/")[-1]
    if platform == "instagram" and "instagram.com/" in h:
        h = h.rstrip("/").split("/")[-1]
    if len(h) > 80 or any(c.isspace() for c in h):
        raise HTTPException(400, "That does not look like a valid handle.")
    return h


def _stats(db: Session, workspace_id: str, platform: str) -> dict:
    rows = (
        db.query(HistoricalPost)
        .filter(HistoricalPost.workspace_id == workspace_id, HistoricalPost.platform == platform)
        .all()
    )
    rows_with_views = [row for row in rows if row.views is not None]
    views = sum(row.views or 0 for row in rows_with_views)
    engagements = sum(
        (row.likes or 0) + (row.comments or 0) + (row.shares or 0)
        for row in rows_with_views
    )
    followers = max((row.followers_at_publish or 0) for row in rows) if rows else 0
    return {
        "post_count": len(rows),
        "avg_views": int(views / len(rows_with_views)) if rows_with_views else None,
        "total_views": views if rows_with_views else None,
        "engagement_rate": round(engagements / views, 4) if views else (0.0 if rows_with_views else None),
        "followers": followers,
    }


def _serialize(acc: SocialAccount, db: Session) -> dict:
    stats = _stats(db, acc.workspace_id, acc.platform)
    meta = PLATFORMS.get(acc.platform, {})
    is_live_linked = acc.mode == "oauth" and bool(acc.external_id)
    if is_live_linked and acc.platform == "instagram":
        evidence = (
            "Instagram professional account linked through Meta OAuth. "
            "Profile counters come from Instagram; post history is synced from Instagram API where available."
        )
    elif is_live_linked and acc.platform == "youtube":
        evidence = "YouTube channel linked through OAuth; profile counters come from YouTube."
    elif stats["post_count"]:
        evidence = "Derived from imported historical posts"
    else:
        evidence = "No imported history for this account yet"
    return {
        "id": acc.id,
        "platform": acc.platform,
        "label": meta.get("label", acc.platform.title()),
        "product": meta.get("product", ""),
        "handle": acc.handle,
        "display_name": acc.display_name,
        "status": acc.status,
        "mode": acc.mode,
        "scopes": [s for s in (acc.scopes or "").split(",") if s],
        "followers": acc.followers if is_live_linked else (acc.followers or stats["followers"]),
        "post_count": acc.post_count if is_live_linked else stats["post_count"],
        "avg_views": acc.avg_views if is_live_linked else stats["avg_views"],
        "total_views": stats["total_views"],
        "engagement_rate": acc.engagement_rate if is_live_linked else stats["engagement_rate"],
        "live_followers": acc.followers if is_live_linked else None,
        "external_id": acc.external_id if is_live_linked else None,
        "last_synced_at": acc.last_synced_at,
        "connected_at": acc.connected_at,
        "evidence": evidence,
    }


def _configured(platform: str) -> bool:
    meta = PLATFORMS[platform]
    return bool(os.getenv(meta["client_id_env"], "")) and bool(os.getenv(meta["client_secret_env"], ""))


@router.get("/accounts")
def list_accounts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    rows = (
        db.query(SocialAccount)
        .filter(SocialAccount.workspace_id == ws_id)
        .order_by(SocialAccount.connected_at.desc())
        .all()
    )
    return [_serialize(a, db) for a in rows]


@router.get("/summary")
def summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    rows = db.query(SocialAccount).filter(SocialAccount.workspace_id == ws_id).all()
    platforms = {r.platform: _serialize(r, db) for r in rows}
    return {
        "connected": len(rows),
        "platforms": platforms,
        "needs_attention": [r.platform for r in rows if r.status != "connected"],
    }


@router.get("/providers")
def providers(user=Depends(get_current_user)):
    return [
        {
            "platform": p,
            "label": meta["label"],
            "product": meta["product"],
            "configured": _configured(p),
            "mode": "oauth" if _configured(p) else "sandbox",
            "required_env": [meta["client_id_env"], meta["client_secret_env"]],
            "scopes": meta["scope"].split(","),
            "note": (
                "OAuth credentials detected. You can authorise a real account."
                if _configured(p)
                else "No OAuth credentials on this server. Connect in sandbox mode: the handle and imported history are used, and publishing stays simulated."
            ),
        }
        for p, meta in PLATFORMS.items()
    ]


@router.post("/accounts")
def connect(payload: ConnectIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    platform = payload.platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "Platform must be instagram or youtube.")
    mode = payload.mode if payload.mode in ("sandbox", "oauth") else "sandbox"
    if mode == "oauth" and not _configured(platform):
        raise HTTPException(400, "OAuth is not configured on this server. Use sandbox mode or set the provider credentials.")

    ws_id = get_workspace_id(user, db)
    handle = _norm_handle(platform, payload.handle)
    existing = (
        db.query(SocialAccount)
        .filter(SocialAccount.workspace_id == ws_id, SocialAccount.platform == platform)
        .first()
    )
    if existing:
        existing.handle = handle
        existing.display_name = payload.display_name or handle
        existing.status = "connected"
        existing.mode = mode
        existing.last_synced_at = datetime.utcnow()
        acc = existing
    else:
        acc = SocialAccount(
            workspace_id=ws_id,
            platform=platform,
            handle=handle,
            display_name=payload.display_name or handle,
            status="connected",
            mode=mode,
            scopes=PLATFORMS[platform]["scope"],
            last_synced_at=datetime.utcnow(),
        )
        db.add(acc)
    db.commit()
    db.refresh(acc)
    return _serialize(acc, db)


def _upsert_live_media(db: Session, workspace_id: str, live: dict) -> None:
    """Store returned Instagram media and preserve unavailable metrics as unknown."""
    for item in live.get("media") or []:
        post_id = item.get("post_id")
        if not post_id:
            continue
        row = (
            db.query(HistoricalPost)
            .filter(
                HistoricalPost.workspace_id == workspace_id,
                HistoricalPost.platform == "instagram",
                HistoricalPost.post_id == post_id,
            )
            .first()
        )
        is_new = row is None
        if is_new:
            row = HistoricalPost(
                workspace_id=workspace_id,
                platform="instagram",
                post_id=post_id,
                views=null(),
                shares=null(),
                saves=null(),
                reach=null(),
                impressions=null(),
                follows=null(),
                profile_visits=null(),
                avg_watch_seconds=null(),
                retention=null(),
                followers_at_publish=null(),
            )
            db.add(row)
        row.caption = item.get("caption") or ""
        row.title = item.get("title") or ""
        row.content_type = item.get("content_type") or "post"
        if item.get("published_at"):
            try:
                row.published_at = datetime.fromisoformat(item["published_at"])
            except (TypeError, ValueError):
                pass
        for key in ("views", "likes", "comments", "shares", "saves", "reach"):
            value = item.get(key)
            if value is not None:
                setattr(row, key, int(value))
            elif is_new:
                # Do not let ORM column defaults turn an unsupported or
                # unavailable provider metric into a misleading zero.
                setattr(row, key, null())



@router.post("/accounts/{account_id}/sync")
def sync(account_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    acc = (
        db.query(SocialAccount)
        .filter(SocialAccount.id == account_id, SocialAccount.workspace_id == ws_id)
        .first()
    )
    if not acc:
        raise HTTPException(404, "Account not found")

    live = None
    tokens = None
    if acc.mode == "oauth" and acc.credential_ref:
        tokens = oauth_service.load_tokens(db, ws_id, acc.platform)
        if tokens:
            live = oauth_service.fetch_live_stats(acc.platform, tokens)
            if acc.platform == "instagram" and live:
                oauth_service.store_tokens(db, ws_id, acc.platform, tokens)
            elif live and live.get("refreshed_password_grant"):
                oauth_service.store_tokens(db, ws_id, acc.platform, tokens)
        else:
            acc.status = "needs_reauth"

    stats = _stats(db, ws_id, acc.platform)
    if live:
        if acc.platform == "instagram":
            acc.handle = live.get("handle") or acc.handle
            acc.display_name = live.get("display_name") or acc.display_name
            acc.external_id = live.get("external_id") or acc.external_id
            _upsert_live_media(db, ws_id, live)
        acc.followers = int(live.get("followers", acc.followers) or 0)
        if "post_count" in live:
            acc.post_count = int(live.get("post_count") or 0)
        if "avg_views" in live:
            acc.avg_views = int(live.get("avg_views") or 0) if live.get("view_metrics_available", 1) else None
        if "engagement_rate" in live:
            acc.engagement_rate = float(live.get("engagement_rate") or 0)
        acc.status = "connected"
        acc_source = "live Instagram API data" if acc.platform == "instagram" else "live YouTube API data"
    else:
        # If OAuth is already linked, keep its last known provider counters when
        # a live call fails; do not replace them with unrelated CSV history.
        if acc.mode != "oauth":
            acc.followers = stats["followers"]
            acc.avg_views = stats["avg_views"]
            acc.engagement_rate = stats["engagement_rate"]
        acc.status = "connected" if acc.status != "needs_reauth" else acc.status
        acc_source = "imported history"
    acc.last_synced_at = datetime.utcnow()
    db.commit()
    body = _serialize(acc, db)
    body["sync_source"] = acc_source
    if acc.platform == "instagram" and live:
        body["live_metrics"] = {
            key: live.get(key)
            for key in ("total_views", "total_likes", "total_comments", "total_reach", "view_metrics_available", "data_source")
        }
    if acc.platform == "instagram" and not live:
        body["sync_note"] = (
            "Instagram live metrics were unavailable. Reconnect Instagram and approve the requested "
            "instagram_manage_insights, instagram_basic, pages_show_list, and pages_read_engagement permissions."
        )
    return body


@router.delete("/accounts/{account_id}")
def disconnect(account_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    acc = (
        db.query(SocialAccount)
        .filter(SocialAccount.id == account_id, SocialAccount.workspace_id == ws_id)
        .first()
    )
    if not acc:
        raise HTTPException(404, "Account not found")
    if acc.mode == "oauth" and acc.credential_ref:
        oauth_service.mark_revoked(db, ws_id, acc.platform)
    platform = acc.platform
    db.delete(acc)
    db.commit()
    return {"disconnected": True, "platform": platform}


def _oauth_redirect_uri(request: Request, platform: str) -> str:
    base = settings.OAUTH_REDIRECT_BASE or os.getenv("OAUTH_REDIRECT_BASE", "")
    if base:
        return base.rstrip("/") + f"/social/oauth/{platform}/callback"
    return str(request.base_url).rstrip("/") + f"/social/oauth/{platform}/callback"


def _upsert_oauth_account(
    db: Session,
    ws_id: str,
    platform: str,
    handle: str,
    display_name: str,
    credential_id: str,
    external_id: str = "",
    followers: int = 0,
    post_count: int = 0,
) -> SocialAccount:
    existing = (
        db.query(SocialAccount)
        .filter(SocialAccount.workspace_id == ws_id, SocialAccount.platform == platform)
        .first()
    )
    if existing:
        existing.handle = handle
        existing.display_name = display_name or handle
        existing.external_id = external_id or existing.external_id or ""
        existing.status = "connected"
        existing.mode = "oauth"
        existing.credential_ref = credential_id
        existing.scopes = PLATFORMS[platform]["scope"]
        existing.followers = int(followers or 0)
        existing.post_count = int(post_count or 0)
        existing.last_synced_at = datetime.utcnow()
        acc = existing
    else:
        acc = SocialAccount(
            workspace_id=ws_id,
            platform=platform,
            handle=handle,
            display_name=display_name or handle,
            external_id=external_id or "",
            status="connected",
            mode="oauth",
            scopes=PLATFORMS[platform]["scope"],
            credential_ref=credential_id,
            followers=int(followers or 0),
            post_count=int(post_count or 0),
            last_synced_at=datetime.utcnow(),
        )
        db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/oauth/{platform}/start")
def oauth_start(platform: str, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    platform = platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "Unsupported platform")
    if not _configured(platform):
        raise HTTPException(
            400,
            "OAuth is not configured. Add the provider client id and secret to the backend environment, "
            "then restart. Sandbox connection is available now.",
        )
    meta = PLATFORMS[platform]
    ws_id = get_workspace_id(user, db)
    redirect_uri = _oauth_redirect_uri(request, platform)
    row = oauth_service.create_state(db, ws_id, platform, redirect_uri)
    params = {
        "client_id": os.getenv(meta["client_id_env"], ""),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": meta["scope"],
        "state": row.state,
    }
    if platform == "youtube":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return {"authorize_url": f"{meta['auth_url']}?{urlencode(params)}", "state": row.state}


def _frontend_redirect(kind: str, platform: str, detail: str) -> RedirectResponse:
    base = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(f"{base}/app/integrations?oauth_{kind}={platform}&detail={detail}", status_code=302)


@router.get("/oauth/{platform}/callback")
def oauth_callback(
    platform: str,
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Provider lands the browser here.

    The code is exchanged server-side for tokens, tokens are stored encrypted
    at rest, and the workspace account is marked OAuth-connected. The browser
    is sent back to the frontend either way — never a raw token.
    """
    platform = platform.lower()
    if platform not in PLATFORMS:
        raise HTTPException(400, "Unsupported platform")
    if error:
        return _frontend_redirect("error", platform, f"provider:{error}")
    if not code:
        return _frontend_redirect("error", platform, "missing_code")
    binding = oauth_service.consume_state(db, state, platform)
    if not binding:
        return _frontend_redirect("error", platform, "state_failed")

    try:
        tokens = oauth_service.exchange_code(platform, code, binding["redirect_uri"])
    except Exception:
        import logging

        logging.getLogger("socialboost.oauth").info(
            "token exchange failed for %s", platform, exc_info=True
        )
        return _frontend_redirect("error", platform, "exchange_failed")
    if not tokens.get("access_token"):
        return _frontend_redirect("error", platform, "no_token")

    handle = ""
    display_name = ""
    external_id = ""
    followers = 0
    post_count = 0
    identity = {}
    try:
        identity = oauth_service.fetch_identity(platform, tokens["access_token"])
        handle = identity.get("handle") or ""
        display_name = identity.get("display_name") or ""
        external_id = identity.get("external_id") or ""
        followers = int(identity.get("followers", 0) or 0)
        post_count = int(identity.get("post_count", 0) or 0)
        if platform == "instagram":
            # Keep the linked Instagram User ID and Page token encrypted with
            # the OAuth token payload. A Page's own counters are never used as IG metrics.
            tokens["instagram_user_id"] = identity.get("instagram_user_id") or external_id
            tokens["page_access_token"] = identity.get("page_access_token") or ""
            tokens["page_id"] = identity.get("page_id") or ""
            tokens["instagram_handle"] = handle
            tokens["instagram_display_name"] = display_name
            tokens["instagram_profile_picture_url"] = identity.get("profile_picture_url") or ""
    except oauth_service.InstagramPagePermissionMissing:
        import logging

        logging.getLogger("socialboost.oauth").warning(
            "Meta token is missing pages_show_list for Instagram OAuth workspace %s",
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "instagram_pages_permission_missing")
    except oauth_service.InstagramPagesNotFound:
        import logging

        logging.getLogger("socialboost.oauth").warning(
            "Meta returned no manageable Facebook Pages for Instagram OAuth workspace %s "
            "despite a granted pages_show_list permission; check Page access and Business Portfolio assignment",
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "instagram_pages_not_found")
    except oauth_service.InstagramAccountNotFound:
        import logging

        logging.getLogger("socialboost.oauth").info(
            "Meta returned Pages, but none exposed a linked Instagram professional account for workspace %s",
            binding["workspace_id"],
            exc_info=True,
        )
        if platform == "instagram":
            return _frontend_redirect("error", platform, "instagram_business_account_not_found")
        return _frontend_redirect("error", platform, "identity_not_found")
    except Exception:
        import logging

        # Keep the provider's actual error in server logs. Do not mislabel
        # permission/API failures as a missing Instagram account in the UI.
        logging.getLogger("socialboost.oauth").exception(
            "provider identity lookup failed for %s in workspace %s",
            platform,
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "graph_lookup_failed")

    if not handle:
        handle = f"{platform}-user"
    if not display_name:
        display_name = handle

    cred = oauth_service.store_tokens(db, binding["workspace_id"], platform, tokens)
    acc = _upsert_oauth_account(
        db,
        binding["workspace_id"],
        platform,
        handle,
        display_name,
        cred.id,
        external_id=external_id,
        followers=followers,
        post_count=post_count,
    )

    return _frontend_redirect("connected", platform, "")
