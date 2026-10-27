import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text
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


class OAuthState(Base):
    """Short-lived CSRF token binding an OAuth round-trip to one workspace.

    Rows are deleted on use and expire quickly; the callback must find a
    matching live row or the authorisation is rejected.
    """

    __tablename__ = "oauth_states"
    id = Column(String, primary_key=True, default=uid)
    state = Column(String, nullable=False, unique=True, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False)
    redirect_uri = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class OAuthCredential(Base):
    """Per-workspace provider tokens, encrypted at rest.

    ``payload`` is a Fernet-encrypted JSON document (access token, refresh
    token, expiry). Raw tokens never go through the API responses and never
    sit in ``social_accounts`` — that table only carries ``credential_ref``.
    """

    __tablename__ = "oauth_credentials"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False)  # instagram | youtube
    payload = Column(Text, nullable=False)
    status = Column(String, default="active")  # active | expired | revoked
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
