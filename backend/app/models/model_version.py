import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    name = Column(String, nullable=False)
    version = Column(String, default="1.0")
    metrics = Column(JSON, default=dict)
    path = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)