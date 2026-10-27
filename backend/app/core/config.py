import os
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

# Paths in .env are written relative to the project root (the parent of
# backend/). Resolving them against that root means the server behaves the same
# whether it is started from the repo root or from backend/.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


class Settings(BaseSettings):
    APP_NAME: str = "SocialBoost AI"
    ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = Field(default="change-me-in-production-please-use-long-random")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = "sqlite:///./backend/socialboost.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 200
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    DEMO_MODE: bool = True
    MODEL_DIR: str = "./ml/artifacts"
    FRONTEND_URL: str = "http://localhost:3000"

    # Publishing. Real provider publishing is not implemented, so non-sandbox
    # scheduled jobs must never be reported as published.
    LIVE_PUBLISHING_ENABLED: bool = False

    # Minimum rows required before a model will train.
    MIN_TRAINING_ROWS: int = 10

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def resolved_upload_dir(self) -> str:
        return _resolve(self.UPLOAD_DIR)

    @property
    def resolved_model_dir(self) -> str:
        return _resolve(self.MODEL_DIR)

    @property
    def resolved_database_url(self) -> str:
        url = self.DATABASE_URL
        if not url.startswith("sqlite"):
            return url
        prefix, _, raw = url.partition(":///")
        if not raw or raw == ":memory:" or os.path.isabs(raw):
            return url
        return f"{prefix}:///{_resolve(raw)}"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
