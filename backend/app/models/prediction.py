import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    platform = Column(String, nullable=False)
    performance_score = Column(Float, nullable=True)
    expected_views_low = Column(Integer, nullable=True)
    expected_views_high = Column(Integer, nullable=True)
    expected_engagement_rate = Column(Float, nullable=True)
    category = Column(String, default="typical")
    confidence = Column(Float, default=0.0)
    factors = Column(JSON, default=list)
    model_version = Column(String, default="none")
    created_at = Column(DateTime, default=datetime.utcnow)


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    platform = Column(String, nullable=False)
    caption = Column(Text, default="")
    title = Column(String, default="")
    description = Column(Text, default="")
    hashtags = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    video = relationship("Video", back_populates="drafts")