from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.user import UserPreference
from .deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

THEMES = {"light", "dark"}
ALLOWED_PLATFORMS = {"instagram", "youtube"}


class PrefIn(BaseModel):
    theme: str | None = None
    timezone: str | None = None
    platforms: str | None = None
    target_audience: str | None = None


def _pref_for(user, db: Session) -> UserPreference:
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if not pref:
        pref = UserPreference(user_id=user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _serialize(pref: UserPreference) -> dict:
    return {
        "theme": pref.theme,
        "timezone": pref.timezone,
        "platforms": pref.platforms,
        "target_audience": pref.target_audience,
    }


@router.get("/preferences")
def get_prefs(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize(_pref_for(user, db))


@router.put("/preferences")
def update_prefs(payload: PrefIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    pref = _pref_for(user, db)

    if payload.theme is not None:
        theme = payload.theme.strip().lower()
        if theme not in THEMES:
            raise HTTPException(400, "theme must be 'light' or 'dark'")
        pref.theme = theme

    if payload.timezone is not None:
        tz = payload.timezone.strip()
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(400, f"Unknown timezone '{tz}'. Use an IANA name such as Europe/London.")
        pref.timezone = tz
        user.timezone = tz

    if payload.platforms is not None:
        items = [p.strip().lower() for p in payload.platforms.split(",") if p.strip()]
        unknown = sorted(set(items) - ALLOWED_PLATFORMS)
        if unknown:
            raise HTTPException(400, f"Unsupported platform(s): {', '.join(unknown)}")
        # Keep a stable, de-duplicated order.
        ordered = [p for p in ("instagram", "youtube") if p in set(items)]
        pref.platforms = ",".join(ordered)

    if payload.target_audience is not None:
        audience = payload.target_audience.strip()
        if len(audience) > 300:
            raise HTTPException(400, "target_audience is limited to 300 characters")
        pref.target_audience = audience

    db.commit()
    db.refresh(pref)
    return _serialize(pref)
