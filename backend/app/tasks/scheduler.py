"""
AInsider Tracker – Background Scheduler
Manages periodic background jobs using APScheduler.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger("ainsider.scheduler")

# Global scheduler instance
scheduler = BackgroundScheduler(
    job_defaults={
        "coalesce": True,  # Combine missed runs into one
        "max_instances": 1,  # Prevent overlapping runs
        "misfire_grace_time": 300,  # 5 min grace period
    }
)


def _run_pipeline_job():
    """Wrapper for the pipeline job."""
    from app.services.pipeline import run_pipeline
    from app.routers.system import add_log

    try:
        add_log("INFO", "Scheduled pipeline run starting...")
        stats = run_pipeline()
        add_log("INFO", f"Scheduled pipeline complete: {stats.get('new_trades', 0)} new trades")
    except Exception as e:
        logger.error(f"Scheduled pipeline failed: {e}")
        add_log("ERROR", f"Scheduled pipeline failed: {str(e)[:100]}")


def _run_price_update_job():
    """Wrapper for the price update job."""
    from app.services.price_updater import update_all_prices
    from app.routers.system import add_log

    try:
        add_log("INFO", "Scheduled price update starting...")
        update_all_prices()
        add_log("INFO", "Scheduled price update complete")
    except Exception as e:
        logger.error(f"Scheduled price update failed: {e}")
        add_log("ERROR", f"Scheduled price update failed: {str(e)[:100]}")


def start_scheduler():
    """Start the background scheduler with configured jobs."""
    # Pipeline job
    scheduler.add_job(
        _run_pipeline_job,
        trigger=IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
        id="pipeline_job",
        name="Trade Data Pipeline",
        replace_existing=True,
    )
    logger.info(f"Pipeline job scheduled every {settings.SCHEDULER_INTERVAL_MINUTES} minutes")

    # Price update job
    scheduler.add_job(
        _run_price_update_job,
        trigger=IntervalTrigger(minutes=settings.PRICE_UPDATE_INTERVAL_MINUTES),
        id="price_update_job",
        name="Stock Price Update",
        replace_existing=True,
    )
    logger.info(f"Price update job scheduled every {settings.PRICE_UPDATE_INTERVAL_MINUTES} minutes")

    scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
