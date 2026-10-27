import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=uid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="")
    timezone = Column(String, default="UTC")
    niche = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, default=uid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="My Studio")
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="workspaces")
    videos = relationship("Video", back_populates="workspace", cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="workspace", cascade="all, delete-orphan")
    social_accounts = relationship("SocialAccount", back_populates="workspace", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(String, primary_key=True, default=uid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    theme = Column(String, default="light")
    timezone = Column(String, default="UTC")
    platforms = Column(String, default="instagram,youtube")
    target_audience = Column(String, default="")
    user = relationship("User", back_populates="preferences")