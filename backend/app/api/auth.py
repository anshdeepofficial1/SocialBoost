from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.security import create_access_token, hash_password, verify_password
from ..db.session import get_db
from ..models.user import User, UserPreference, Workspace
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 6
# bcrypt only considers the first 72 bytes of a password. Reject longer input
# instead of silently ignoring part of it.
MAX_PASSWORD_BYTES = 72


class SignupIn(BaseModel):
    email: str
    password: str
    full_name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


@router.post("/signup", response_model=TokenOut)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Enter a valid email address")
    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(payload.password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(400, f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    db.add(user)
    try:
        db.flush()
        db.add(Workspace(owner_id=user.id, name="My Studio"))
        db.add(UserPreference(user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Email already registered")
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(400, "Invalid credentials")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "timezone": user.timezone,
        "niche": user.niche,
    }
