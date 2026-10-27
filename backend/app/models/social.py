import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from ..db.session import Base


def uid():
    return str(uuid.uuid4())


class SocialAccount(Base):
    """A linked Instagram or YouTube identity.

    Sandbox mode records the handle and derives metrics from imported
    historical posts. OAuth mode would store a vault reference, never a
    raw access token in this table.
    """

    __tablename__ = "social_accounts"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    platform = Column(String, nullable=False)  # instagram | youtube
    handle = Column(String, nullable=False)
    display_name = Column(String, default="")
    external_id = Column(String, default="")
    status = Column(String, default="connected")  # connected | needs_reauth | disconnected
    mode = Column(String, default="sandbox")  # sandbox | oauth
    scopes = Column(String, default="")
    credential_ref = Column(String, nullable=True)
    followers = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    avg_views = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    last_synced_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    workspace = relationship("Workspace", back_populates="social_accounts")
