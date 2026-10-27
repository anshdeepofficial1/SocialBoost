import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    fps = Column(Float, default=0.0)
    aspect_ratio = Column(String, default="")
    has_audio = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    workspace = relationship("Workspace", back_populates="videos")
    jobs = relationship("AnalysisJob", back_populates="video", cascade="all, delete-orphan")
    drafts = relationship("Draft", back_populates="video", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=uid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    status = Column(String, default="queued")  # queued, processing, done, failed
    progress = Column(Integer, default=0)
    current_step = Column(String, default="queued")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    video = relationship("Video", back_populates="jobs")
    result = relationship("AnalysisResult", back_populates="job", uselist=False, cascade="all, delete-orphan")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), unique=True, nullable=False)
    technical = Column(JSON, default=dict)
    hook = Column(JSON, default=dict)
    metadata_analysis = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    job = relationship("AnalysisJob", back_populates="result")