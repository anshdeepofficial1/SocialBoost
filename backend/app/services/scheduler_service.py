"""Scheduled publishing.

Sandbox jobs are simulated and stored with the status ``sandbox``. Live
publishing is not implemented in this build, so a non-sandbox job is marked
``failed`` with a clear reason instead of being reported as published.
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from ..core.config import settings
from ..db.session import SessionLocal
from ..models.calendar import ScheduledPost

log = logging.getLogger("socialboost.scheduler")

scheduler = BackgroundScheduler(timezone="UTC")


def publish_job(post_id: str) -> None:
    db = SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != "scheduled":
            return
        post.attempts = (post.attempts or 0) + 1
        if post.is_sandbox:
            post.status = "sandbox"
            post.last_error = None
            log.info("simulated publish for post %s", post.id)
        elif not settings.LIVE_PUBLISHING_ENABLED:
            post.status = "failed"
            post.last_error = (
                "Live publishing is disabled on this server. Nothing was sent to the platform. "
                "Connect provider credentials and enable live publishing to make this real."
            )
            log.warning("refused live publish for post %s", post.id)
        else:
            post.status = "failed"
            post.last_error = "No publishing provider is implemented in this build."
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if post:
            post.status = "failed"
            post.last_error = str(exc)
            db.commit()
    finally:
        db.close()


def schedule_post(post: ScheduledPost) -> None:
    run_at = post.scheduled_at
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)

    # A time in the past is valid input (backfilling), but APScheduler treats it
    # as a missed run and skips it. Fire shortly after scheduling instead.
    now = datetime.now(timezone.utc)
    if run_at <= now:
        run_at = now + timedelta(seconds=1)

    scheduler.add_job(
        publish_job,
        "date",
        run_date=run_at,
        args=[post.id],
        id=post.id,
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )


def cancel_job(post_id: str) -> None:
    try:
        scheduler.remove_job(post_id)
    except Exception:
        pass


def restore_pending_jobs() -> int:
    """Re-register jobs for posts still waiting to run after a restart.

    A post whose time passed while the server was offline is scheduled
    immediately by ``schedule_post`` so it is resolved rather than stranded.
    """
    db = SessionLocal()
    count = 0
    try:
        pending = (
            db.query(ScheduledPost)
            .filter(ScheduledPost.status == "scheduled")
            .all()
        )
        for post in pending:
            schedule_post(post)
            count += 1
        log.info("restored %d scheduled job(s)", count)
    except Exception as exc:  # pragma: no cover - defensive
        log.error("failed to restore jobs: %s", exc)
    finally:
        db.close()
    return count


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
        restore_pending_jobs()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
