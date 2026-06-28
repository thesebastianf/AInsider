"""
AInsider Tracker – System Router
Health check, system stats, and live logs for the Developer Tab.
"""

import time
from collections import deque
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Trade, TargetPerson, Subscription, AssetPerformance, LLMConfig
from app.schemas import SystemStats, LogEntry, LogList

router = APIRouter(prefix="/api", tags=["System"])

# ─── Application start time ──────────────────────────────────
APP_START_TIME = time.time()

# ─── In-memory log buffer (max 500 entries) ───────────────────
log_buffer: deque[LogEntry] = deque(maxlen=500)


def add_log(level: str, message: str):
    """Add a log entry to the in-memory buffer."""
    entry = LogEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level=level,
        message=message,
    )
    log_buffer.append(entry)


@router.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/system/stats", response_model=SystemStats)
def get_system_stats(db: Session = Depends(get_db)):
    """Get system statistics for the developer dashboard."""
    total_trades = db.query(func.count(Trade.id)).scalar() or 0
    total_persons = db.query(func.count(TargetPerson.id)).scalar() or 0
    total_subscriptions = db.query(func.count(Subscription.id)).scalar() or 0
    total_tickers = db.query(func.count(AssetPerformance.ticker)).scalar() or 0
    uptime_seconds = time.time() - APP_START_TIME

    # Check active LLM provider
    active_llm = db.query(LLMConfig).filter(LLMConfig.is_active == True).first()  # noqa: E712
    llm_status = "configured" if active_llm else "not configured"

    from app.routers.settings import _runtime_overrides
    last_run = _runtime_overrides.get("last_pipeline_run")

    return SystemStats(
        total_trades=total_trades,
        total_persons=total_persons,
        total_subscriptions=total_subscriptions,
        total_tickers=total_tickers,
        uptime_seconds=uptime_seconds,
        last_pipeline_run=last_run,
        api_status="online",
        db_status="connected",
        llm_status=llm_status,
    )


@router.get("/system/logs", response_model=LogList)
def get_system_logs(limit: int = 100):
    """Get recent system logs from the in-memory buffer."""
    logs = list(log_buffer)[-limit:]
    return LogList(logs=logs)


@router.post("/system/trigger-pipeline")
def trigger_pipeline():
    """Manually trigger the data pipeline."""
    from app.services.pipeline import run_pipeline
    try:
        add_log("INFO", "Manual pipeline trigger requested")
        run_pipeline()
        add_log("INFO", "Manual pipeline run completed")
        return {"status": "success", "message": "Pipeline triggered successfully"}
    except Exception as e:
        add_log("ERROR", f"Pipeline error: {str(e)}")
        return {"status": "error", "message": str(e)}
