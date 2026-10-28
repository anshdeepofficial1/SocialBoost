import os
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


def normalize_database_url(value: str) -> str:
    """Normalize hosted-Postgres URLs to SQLAlchemy's psycopg v3 driver."""
    url = (value or "").strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    APP_NAME: str = "SocialBoost AI"
    ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = Field(default="change-me-in-production-please-use-long-random")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # SQLite is convenient locally. Production must use durable PostgreSQL or
    # a SQLite file on an explicitly mounted persistent disk.
    DATABASE_URL: str = "sqlite:///./backend/socialboost.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 200
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    DEMO_MODE: bool = True
    MODEL_DIR: str = "./ml/artifacts"
    FRONTEND_URL: str = "http://localhost:3000"
    OAUTH_REDIRECT_BASE: str = ""
    LIVE_PUBLISHING_ENABLED: bool = False
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
        url = normalize_database_url(self.DATABASE_URL)
        if not url.startswith("sqlite"):
            return url
        prefix, _, raw = url.partition(":///")
        if not raw or raw == ":memory:" or os.path.isabs(raw):
            return url
        return f"{prefix}:///{_resolve(raw)}"

    @property
    def database_backend(self) -> str:
        url = self.resolved_database_url
        if url.startswith("postgresql"):
            return "postgresql"
        if url.startswith("sqlite"):
            return "sqlite"
        return "other"

    @property
    def sqlite_path_is_data_mount(self) -> bool:
        return self.resolved_database_url.startswith("sqlite:////data/")

    @property
    def using_default_secret(self) -> bool:
        return self.SECRET_KEY.startswith("change-me-in-production")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
