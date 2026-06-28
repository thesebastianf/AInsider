"""
AInsider Tracker – Background Scheduler
Manages periodic background jobs using APScheduler.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

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


def _run_backup_job():
    """Wrapper for the weekly database backup job."""
    from app.services.backup import run_backup
    from app.routers.system import add_log

    try:
        add_log("INFO", "Scheduled weekly database backup starting...")
        result = run_backup()
        if result.get("status") == "success":
            size_mb = result.get("size_bytes", 0) / (1024 * 1024)
            add_log("INFO", f"Weekly backup complete: {result['filename']} ({size_mb:.2f} MB)")
        else:
            add_log("ERROR", f"Weekly backup failed: {result.get('message', 'unknown error')}")
    except Exception as e:
        logger.error(f"Scheduled backup failed: {e}")
        add_log("ERROR", f"Scheduled backup failed: {str(e)[:100]}")


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

    # Weekly backup job — every Sunday at 03:00
    scheduler.add_job(
        _run_backup_job,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="backup_job",
        name="Weekly Database Backup",
        replace_existing=True,
    )
    logger.info("Weekly backup job scheduled for Sunday 03:00")

    scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
