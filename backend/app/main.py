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
from .services.scheduler_service import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("socialboost")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    start_scheduler()
    log.info("SocialBoost AI ready (env=%s, live_publishing=%s)", settings.ENV, settings.LIVE_PUBLISHING_ENABLED)
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
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
