import os
from datetime import datetime, timedelta
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
from ..services import oauth_service, ml_service, growth_model
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
    credential_tokens = (oauth_service.load_tokens(db, acc.workspace_id, acc.platform) if is_live_linked else None) or {}
    profile_picture_url = credential_tokens.get("instagram_profile_picture_url") or credential_tokens.get("youtube_profile_picture_url") or credential_tokens.get("profile_picture_url") or ""
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
        "profile_picture_url": profile_picture_url,
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


def _upsert_live_media(db: Session, workspace_id: str, platform: str, live: dict) -> int:
    """Upsert provider-returned media into the common historical-post table.

    Return the number of identifiable provider items processed, so the sync
    response can show whether data actually entered the shared dataset.
    """
    processed = 0
    for item in live.get("media") or []:
        post_id = item.get("post_id")
        if not post_id:
            continue
        row = (
            db.query(HistoricalPost)
            .filter(
                HistoricalPost.workspace_id == workspace_id,
                HistoricalPost.platform == platform,
                HistoricalPost.post_id == post_id,
            )
            .first()
        )
        is_new = row is None
        if is_new:
            row = HistoricalPost(
                workspace_id=workspace_id, platform=platform, post_id=post_id,
                views=null(), likes=null(), comments=null(), shares=null(), saves=null(),
                reach=null(), impressions=null(), follows=null(), profile_visits=null(),
                avg_watch_seconds=null(), retention=null(), followers_at_publish=null(),
            )
            db.add(row)
        row.caption = item.get("caption") or ""
        row.title = (item.get("title") or item.get("caption") or "")[:500]
        row.content_type = item.get("content_type") or ("reel" if platform == "instagram" else "video")
        duration = item.get("duration_seconds")
        if duration is not None:
            row.duration_seconds = float(duration)
        if item.get("published_at"):
            try:
                row.published_at = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
            except (TypeError, ValueError):
                pass
        for key in ("views", "likes", "comments", "shares", "saves", "reach", "impressions"):
            value = item.get(key)
            if value is not None:
                setattr(row, key, int(value))
            elif is_new:
                setattr(row, key, null())
        processed += 1
    return processed


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
    media_processed = 0
    if acc.mode == "oauth" and acc.credential_ref:
        tokens = (
            oauth_service.load_fresh_youtube_tokens(db, ws_id)
            if acc.platform == "youtube"
            else oauth_service.load_tokens(db, ws_id, acc.platform)
        )
        if tokens:
            live = oauth_service.fetch_live_stats(acc.platform, tokens)
            if live:
                oauth_service.store_tokens(db, ws_id, acc.platform, tokens)
        else:
            acc.status = "needs_reauth"

    stats = _stats(db, ws_id, acc.platform)
    if live:
        if acc.platform in ("instagram", "youtube"):
            acc.handle = live.get("handle") or acc.handle
            acc.display_name = live.get("display_name") or acc.display_name
            acc.external_id = live.get("external_id") or acc.external_id
            media_processed = _upsert_live_media(db, ws_id, acc.platform, live)
        acc.followers = int(live.get("followers", acc.followers) or 0)
        if "post_count" in live:
            acc.post_count = int(live.get("post_count") or 0)
        if "avg_views" in live:
            if acc.platform == "instagram":
                acc.avg_views = (
                    int(live.get("avg_views") or 0)
                    if live.get("view_metrics_available", 1)
                    else None
                )
            elif live.get("avg_views") is not None:
                acc.avg_views = int(live["avg_views"])
            elif not acc.avg_views:
                # A zero default is not evidence of zero average views.
                acc.avg_views = None
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
    platform_rows = (
        db.query(HistoricalPost)
        .filter(
            HistoricalPost.workspace_id == ws_id,
            HistoricalPost.platform == acc.platform,
        )
        .all()
    )
    body["history_sync"] = {
        "provider_items_received": len((live or {}).get("media") or []),
        "records_processed": media_processed,
        "stored_platform_posts": len(platform_rows),
        "posts_with_views": sum(1 for row in platform_rows if row.views is not None),
    }

    # Provider-synced media is immediately eligible for supervised training.
    # train_models refuses to fit until enough rows have real view counts.
    if live:
        try:
            available_rows = (
                db.query(HistoricalPost)
                .filter(
                    HistoricalPost.workspace_id == ws_id,
                    HistoricalPost.views.isnot(None),
                )
                .count()
            )
            if available_rows < settings.MIN_TRAINING_ROWS:
                body["model_training"] = {
                    "status": "insufficient_data",
                    "n_samples": available_rows,
                    "required": settings.MIN_TRAINING_ROWS,
                }
            else:
                active_model = ml_service.model_status(ws_id)
                try:
                    trained_at = datetime.fromisoformat(active_model.get("trained_at") or "")
                except (TypeError, ValueError):
                    trained_at = None
                stale_model = (
                    not active_model.get("available")
                    or trained_at is None
                    or datetime.utcnow() - trained_at.replace(tzinfo=None) > timedelta(hours=24)
                    or int(active_model.get("n_samples") or 0) != available_rows
                )
                body["model_training"] = (
                    ml_service.train_models(db, ws_id)
                    if stale_model
                    else {
                        "status": "already_current",
                        "n_samples": available_rows,
                        "version": active_model.get("version"),
                    }
                )
        except Exception:
            import logging
            logging.getLogger("socialboost.ml").exception(
                "automatic training after %s sync failed for workspace %s",
                acc.platform, ws_id,
            )
            body["model_training"] = {
                "status": "failed",
                "message": "Sync completed, but automatic model training failed. Check backend logs.",
            }
    # Train the content-aware growth model from the same account-synced
    # dataset. Reuse a current artifact to avoid repeating heavy training on
    # every request when both accounts are refreshed in quick succession.
    if live:
        try:
            usable_rows = (
                db.query(HistoricalPost)
                .filter(
                    HistoricalPost.workspace_id == ws_id,
                    HistoricalPost.views.isnot(None),
                )
                .count()
            )
            if usable_rows < growth_model.MIN_ROWS:
                body["growth_model_training"] = {
                    "status": "insufficient_data",
                    "n_samples": usable_rows,
                    "required": growth_model.MIN_ROWS,
                }
            else:
                coach_status = growth_model.status(ws_id)
                try:
                    trained_at = datetime.fromisoformat(coach_status.get("trained_at") or "")
                except (TypeError, ValueError):
                    trained_at = None
                stale = (
                    not coach_status.get("available")
                    or trained_at is None
                    or datetime.utcnow() - trained_at.replace(tzinfo=None) > timedelta(hours=24)
                    or int(coach_status.get("n_samples") or 0) != usable_rows
                )
                body["growth_model_training"] = (
                    growth_model.train(db, ws_id)
                    if stale
                    else {
                        "status": "already_current",
                        "n_samples": usable_rows,
                        "version": coach_status.get("version"),
                    }
                )
        except Exception:
            import logging
            logging.getLogger("socialboost.ml").exception(
                "automatic growth-model training after %s sync failed for workspace %s",
                acc.platform, ws_id,
            )
            body["growth_model_training"] = {
                "status": "failed",
                "message": "Account sync completed, but the content-aware growth model could not be refreshed. Check backend logs.",
            }

    if acc.platform == "youtube" and live and media_processed == 0:
        body["sync_note"] = (
            "YouTube channel totals refreshed, but no recent upload records were imported. "
            "Check backend logs for the YouTube recent-video import error; no placeholder posts were created."
        )

    if acc.platform == "instagram" and live:
        body["live_metrics"] = {
            key: live.get(key)
            for key in ("total_views", "total_likes", "total_comments", "total_reach", "view_metrics_available", "data_source")
        }
    if acc.platform == "youtube" and live:
        body["live_metrics"] = {
            key: live.get(key)
            for key in ("total_views", "avg_views", "avg_views_sample_size")
        }
    if acc.platform == "youtube" and not live:
        body["sync_note"] = (
            "YouTube channel statistics could not be refreshed. Reconnect the Google account if its "
            "authorization has expired, then check Render logs for the YouTube Data API error."
        )
    if acc.platform == "instagram" and not live:
        error_type = (tokens or {}).get("_sync_error_type")
        body["sync_error_type"] = error_type
        if acc.status == "needs_reauth":
            body["sync_note"] = (
                "SocialBoost could not decrypt or find the saved Instagram authorization. "
                "Reconnect Instagram once; your saved account and historical records will be kept."
            )
        elif error_type == "HTTPStatusError":
            body["sync_note"] = (
                "Meta rejected the Instagram stats request (HTTP error). The account stays connected "
                "and its last known counters are preserved. Check the Render logs for the Graph API "
                "error code/message before reconnecting; do not disconnect the account yet."
            )
        elif error_type:
            body["sync_note"] = (
                f"Instagram stats sync failed ({error_type}). The last known counters are preserved. "
                "Check the Render logs for the matching 'live stats fetch failed for instagram' entry "
                "to see the exact provider error before changing permissions or reconnecting."
            )
        else:
            body["sync_note"] = (
                "Instagram live metrics could not be refreshed. The last known counters are preserved. "
                "Check the Render logs for the exact sync failure before reconnecting or changing permissions."
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
    avg_views: int | None = None,
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
        if avg_views is not None:
            existing.avg_views = int(avg_views)
        elif not existing.avg_views:
            existing.avg_views = None
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
            avg_views=avg_views,
            last_synced_at=datetime.utcnow(),
        )
        db.add(acc)
        # Force a SQL NULL for an unknown average instead of allowing a Python
        # ORM default to make the UI display a misleading zero.
        db.flush()
        if avg_views is None:
            acc.avg_views = None
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
        # Force account selection during testing and request a refresh token for
        # durable background sync; keep the grant incremental and read-only.
        params["access_type"] = "offline"
        params["prompt"] = "consent select_account"
        params["include_granted_scopes"] = "true"
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
        return _frontend_redirect(
            "error",
            platform,
            "youtube_exchange_failed" if platform == "youtube" else "exchange_failed",
        )
    if not tokens.get("access_token"):
        return _frontend_redirect(
            "error",
            platform,
            "youtube_no_token" if platform == "youtube" else "no_token",
        )

    handle = ""
    display_name = ""
    external_id = ""
    followers = 0
    post_count = 0
    avg_views: int | None = None
    identity = {}
    try:
        identity = oauth_service.fetch_identity(platform, tokens["access_token"])
        handle = identity.get("handle") or ""
        display_name = identity.get("display_name") or ""
        external_id = identity.get("external_id") or ""
        followers = int(identity.get("followers", 0) or 0)
        post_count = int(identity.get("post_count", 0) or 0)
        raw_avg_views = identity.get("avg_views")
        avg_views = int(raw_avg_views) if raw_avg_views is not None else None
        if platform == "instagram":
            # Keep the linked Instagram User ID and Page token encrypted with
            # the OAuth token payload. A Page's own counters are never used as IG metrics.
            tokens["instagram_user_id"] = identity.get("instagram_user_id") or external_id
            tokens["page_access_token"] = identity.get("page_access_token") or ""
            tokens["page_id"] = identity.get("page_id") or ""
            tokens["instagram_handle"] = handle
            tokens["instagram_display_name"] = display_name
            tokens["instagram_profile_picture_url"] = identity.get("profile_picture_url") or ""
        else:
            tokens["youtube_handle"] = handle
            tokens["youtube_display_name"] = display_name
            tokens["youtube_profile_picture_url"] = identity.get("profile_picture_url") or ""
    except oauth_service.YouTubeChannelNotFound:
        import logging

        logging.getLogger("socialboost.oauth").warning(
            "Google authorization completed but no YouTube channel was visible for workspace %s",
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "youtube_channel_not_found")
    except oauth_service.InstagramPagePermissionMissing:
        import logging

        logging.getLogger("socialboost.oauth").warning(
            "Meta token is missing pages_show_list for Instagram OAuth workspace %s",
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "instagram_pages_permission_missing")
    except oauth_service.InstagramBusinessManagementPermissionMissing:
        import logging

        logging.getLogger("socialboost.oauth").warning(
            "Meta token is missing business_management while Page discovery returned empty for workspace %s",
            binding["workspace_id"],
        )
        return _frontend_redirect("error", platform, "instagram_business_management_permission_missing")
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
        return _frontend_redirect(
            "error",
            platform,
            "youtube_identity_lookup_failed" if platform == "youtube" else "graph_lookup_failed",
        )

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
        avg_views=avg_views,
    )

    return _frontend_redirect("connected", platform, "")
