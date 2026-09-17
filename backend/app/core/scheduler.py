"""APScheduler configuration for background recurring jobs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import async_session_factory
from app.services.change_request import change_request_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_scheduled_change_requests_job() -> None:
    """Job run every minute to scan and apply due change requests."""
    try:
        async with async_session_factory() as db:
            applied = await change_request_service.process_scheduled_change_requests(db)
            if applied > 0:
                logger.info("APScheduler processed %d scheduled change request(s)", applied)
    except Exception as exc:
        logger.error("Error executing scheduled change requests job: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Start APScheduler if not already running."""
    if not scheduler.running:
        scheduler.add_job(
            run_scheduled_change_requests_job,
            trigger="interval",
            minutes=1,
            id="process_scheduled_change_requests",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started (scheduled change requests running every 1m)")


def shutdown_scheduler() -> None:
    """Gracefully shutdown scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
