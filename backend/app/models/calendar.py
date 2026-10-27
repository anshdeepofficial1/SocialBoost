import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    platform = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String, default="scheduled")  # scheduled, published, failed, cancelled, sandbox
    caption = Column(Text, default="")
    title = Column(String, default="")
    is_sandbox = Column(Boolean, default=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    workspace = relationship("Workspace", back_populates="scheduled_posts")


class HistoricalPost(Base):
    __tablename__ = "historical_posts"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    post_id = Column(String, default="")
    platform = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=True)
    content_type = Column(String, default="short")
    duration_seconds = Column(Float, default=0.0)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    followers_at_publish = Column(Integer, default=0)
    follows = Column(Integer, default=0)
    profile_visits = Column(Integer, default=0)
    avg_watch_seconds = Column(Float, default=0.0)
    retention = Column(Float, default=0.0)
    caption = Column(Text, default="")
    title = Column(String, default="")
    hashtags = Column(String, default="")
    content_category = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DatasetImport(Base):
    __tablename__ = "dataset_imports"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    filename = Column(String, nullable=False)
    rows_imported = Column(Integer, default=0)
    rows_rejected = Column(Integer, default=0)
    columns = Column(JSON, default=list)
    warnings = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)