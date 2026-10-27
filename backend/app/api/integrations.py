from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.session import get_db
from ..models.social import SocialAccount
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/integrations", tags=["integrations"])

PROVIDER_ENV = {
    "instagram": ("IG_CLIENT_ID", "IG_CLIENT_SECRET"),
    "youtube": ("YT_CLIENT_ID", "YT_CLIENT_SECRET"),
}


@router.get("/status")
def status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Connection state per platform, read from the database.

    Earlier versions hard-coded ``connected: False``. This endpoint now reflects
    real rows so the studio can trust it.
    """
    import os

    ws_id = get_workspace_id(user, db)
    accounts = db.query(SocialAccount).filter(SocialAccount.workspace_id == ws_id).all()
    by_platform = {a.platform: a for a in accounts}

    payload = {}
    for platform, (id_env, secret_env) in PROVIDER_ENV.items():
        acc = by_platform.get(platform)
        payload[platform] = {
            "connected": bool(acc) and acc.status == "connected",
            "configured": bool(os.getenv(id_env, "")) and bool(os.getenv(secret_env, "")),
            "mode": acc.mode if acc else "sandbox",
            "handle": acc.handle if acc else None,
            "status": acc.status if acc else "not_connected",
            "last_synced_at": acc.last_synced_at if acc else None,
        }

    payload["live_publishing_enabled"] = settings.LIVE_PUBLISHING_ENABLED
    payload["note"] = (
        "Sandbox connections record a handle and derive statistics from imported history. "
        "Scheduled publishing is simulated unless live publishing is explicitly enabled."
    )
    return payload
