import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (registers models with SQLAlchemy)
from .api import (
    analysis,
    analytics,
    auth,
    calendar,
    coach,
    datasets,
    drafts,
    integrations,
    predictions,
    settings as settings_api,
    social,
    videos,
    youtube,
)
from .core.config import settings
from .db.schema import ensure_schema
from .db.session import engine
from .services.scheduler_service import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("socialboost")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENV.lower() == "production" and settings.using_default_secret:
        raise RuntimeError(
            "SECRET_KEY is using the development default. Set a stable, private SECRET_KEY "
            "in the backend environment before running production."
        )
    ensure_schema()
    if settings.ENV.lower() == "production" and engine.dialect.name == "sqlite":
        if settings.sqlite_path_is_data_mount:
            log.warning(
                "Production SQLite is configured under /data. Data persistence depends on a "
                "Render persistent disk being mounted at /data."
            )
        else:
            log.error(
                "PRODUCTION DATABASE WARNING: this deployment is using SQLite on the service "
                "filesystem. On Render Free, local database files are lost when the service "
                "spins down or redeploys. Configure DATABASE_URL with durable PostgreSQL, or "
                "attach a paid persistent disk and keep SQLite under its mount path."
            )
    start_scheduler()
    log.info(
        "SocialBoost AI ready (env=%s, database=%s, live_publishing=%s)",
        settings.ENV,
        engine.dialect.name,
        settings.LIVE_PUBLISHING_ENABLED,
    )
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(youtube.router)
app.include_router(analysis.router)
app.include_router(predictions.router)
app.include_router(coach.router)
app.include_router(datasets.router)
app.include_router(calendar.router)
app.include_router(analytics.router)
app.include_router(settings_api.router)
app.include_router(integrations.router)
app.include_router(social.router)
app.include_router(drafts.router)

upload_dir = settings.resolved_upload_dir
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")


@app.get("/health")
def health():
    body = {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "database": engine.dialect.name,
        "database_storage": (
            "managed_postgresql"
            if engine.dialect.name == "postgresql"
            else "sqlite_on_data_mount"
            if settings.sqlite_path_is_data_mount
            else "local_sqlite_file"
        ),
    }
    if settings.ENV.lower() == "production" and engine.dialect.name == "sqlite":
        body["storage_warning"] = (
            "SQLite is file-backed. On Render Free, the local filesystem is ephemeral. "
            "Use PostgreSQL or confirm a persistent disk is mounted at /data."
        )
    return body
