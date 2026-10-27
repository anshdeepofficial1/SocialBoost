import os
import secrets
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..models.social import SocialAccount
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/social", tags=["social"])

PLATFORMS = {
    "instagram": {
        "label": "Instagram",
        "product": "Reels",
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "scope": "instagram_basic,instagram_content_publish,pages_show_list",
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
    views = sum(r.views or 0 for r in rows)
    engagements = sum((r.likes or 0) + (r.comments or 0) + (r.shares or 0) for r in rows)
    followers = max((r.followers_at_publish or 0) for r in rows) if rows else 0
    return {
        "post_count": len(rows),
        "avg_views": int(views / len(rows)) if rows else 0,
        "total_views": views,
        "engagement_rate": round(engagements / views, 4) if views else 0.0,
        "followers": followers,
    }


def _serialize(acc: SocialAccount, db: Session) -> dict:
    stats = _stats(db, acc.workspace_id, acc.platform)
    meta = PLATFORMS.get(acc.platform, {})
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
        "followers": acc.followers or stats["followers"],
        "post_count": stats["post_count"],
        "avg_views": stats["avg_views"],
        "total_views": stats["total_views"],
        "engagement_rate": stats["engagement_rate"],
        "last_synced_at": acc.last_synced_at,
        "connected_at": acc.connected_at,
        "evidence": "Derived from imported historical posts" if stats["post_count"] else "No imported history for this account yet",
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
    stats = _stats(db, ws_id, acc.platform)
    acc.followers = stats["followers"]
    acc.avg_views = stats["avg_views"]
    acc.engagement_rate = stats["engagement_rate"]
    acc.last_synced_at = datetime.utcnow()
    acc.status = "connected"
    db.commit()
    return _serialize(acc, db)


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
    db.delete(acc)
    db.commit()
    return {"disconnected": True, "platform": acc.platform}


@router.get("/oauth/{platform}/start")
def oauth_start(platform: str, request: Request, user=Depends(get_current_user)):
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
    state = secrets.token_urlsafe(24)
    redirect_uri = str(request.base_url).rstrip("/") + f"/social/oauth/{platform}/callback"
    params = {
        "client_id": os.getenv(meta["client_id_env"], ""),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": meta["scope"],
        "state": state,
    }
    if platform == "youtube":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return {"authorize_url": f"{meta['auth_url']}?{urlencode(params)}", "state": state}


@router.get("/oauth/{platform}/callback")
def oauth_callback(platform: str, code: str | None = None, error: str | None = None):
    # Deliberately honest: without a token exchange implementation for the
    # configured provider, we do not pretend the account is connected.
    if error:
        raise HTTPException(400, f"Provider returned an error: {error}")
    if not code:
        raise HTTPException(400, "Missing authorization code")
    raise HTTPException(
        501,
        "Token exchange is not implemented in this build. Use sandbox connection; "
        "OAuth start/callback scaffolding is present for a production deployment.",
    )
