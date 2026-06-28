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
    last_price = _runtime_overrides.get("last_price_update")

    # Fetch next run times from APScheduler instance
    next_pipeline = None
    next_price_update = None
    try:
        from app.tasks.scheduler import scheduler
        if scheduler.running:
            pipe_job = scheduler.get_job("pipeline_job")
            if pipe_job:
                next_pipeline = pipe_job.next_run_time
            price_job = scheduler.get_job("price_update_job")
            if price_job:
                next_price_update = price_job.next_run_time
    except Exception:
        pass

    return SystemStats(
        total_trades=total_trades,
        total_persons=total_persons,
        total_subscriptions=total_subscriptions,
        total_tickers=total_tickers,
        uptime_seconds=uptime_seconds,
        last_pipeline_run=last_run,
        next_pipeline_run=next_pipeline,
        last_price_update=last_price,
        next_price_update=next_price_update,
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


@router.get("/system/backups")
def get_backups():
    """List all existing database backups."""
    from app.services.backup import list_backups
    return {"backups": list_backups()}


@router.post("/system/trigger-backup")
def trigger_backup():
    """Manually trigger an immediate database backup."""
    from app.services.backup import run_backup
    try:
        add_log("INFO", "Manual backup trigger requested")
        result = run_backup()
        return result
    except Exception as e:
        add_log("ERROR", f"Manual backup error: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/system/insights")
def get_insights(db: Session = Depends(get_db)):
    """Calculate and return congressional trading platform insights."""
    from datetime import date, timedelta
    
    # 1. Most Active Tracked Person
    active_q = (
        db.query(Trade.target_person_id, func.count(Trade.id).label("trade_count"))
        .group_by(Trade.target_person_id)
        .order_by(func.count(Trade.id).desc())
        .first()
    )
    most_active = None
    if active_q:
        p_id, cnt = active_q
        person = db.query(TargetPerson).filter(TargetPerson.id == p_id).first()
        if person:
            most_active = {
                "name": person.name,
                "photo_url": person.photo_url,
                "trades_count": cnt
            }
            
    if not most_active:
        most_active = {
            "name": "No trades recorded",
            "photo_url": None,
            "trades_count": 0
        }

    # 2. Biggest Outperformer
    outperf = None
    try:
        persons = db.query(TargetPerson).all()
        best_p = None
        best_avg = -999.0
        for p in persons:
            tickers = [t[0] for t in db.query(Trade.ticker).filter(Trade.target_person_id == p.id).distinct().all()]
            if not tickers:
                continue
            perf_vals = db.query(AssetPerformance.ytd_performance_pct).filter(AssetPerformance.ticker.in_(tickers)).all()
            if perf_vals:
                valid_vals = [pv[0] for pv in perf_vals if pv[0] is not None]
                if valid_vals:
                    avg_perf = sum(valid_vals) / len(valid_vals)
                    if avg_perf > best_avg:
                        best_avg = avg_perf
                        best_p = p
        if best_p and best_avg > -100:
            outperf = {
                "name": best_p.name,
                "photo_url": best_p.photo_url,
                "perf_vs_spy": f"+{best_avg:.1f}% vs SPY"
            }
    except Exception:
        pass
        
    if not outperf:
        outperf = {
            "name": "No trades recorded",
            "photo_url": None,
            "perf_vs_spy": "N/A"
        }

    # 3. Hot Stock (60d)
    hot_stock = None
    try:
        sixty_days_ago = date.today() - timedelta(days=60)
        hot_q = (
            db.query(Trade.ticker, func.count(Trade.id).label("trade_count"))
            .filter(Trade.trade_date >= sixty_days_ago)
            .group_by(Trade.ticker)
            .order_by(func.count(Trade.id).desc())
            .first()
        )
        if hot_q:
            tick, cnt = hot_q
            ap = db.query(AssetPerformance).filter(AssetPerformance.ticker == tick).first()
            perf_pct = ap.ytd_performance_pct if ap else 0.0
            hot_stock = {
                "ticker": tick,
                "perf_pct": f"{perf_pct:+.1f}%" if perf_pct else "0.0%",
                "trades_count": cnt
            }
    except Exception:
        pass
        
    if not hot_stock:
        hot_stock = {
            "ticker": "N/A",
            "perf_pct": "N/A",
            "trades_count": 0
        }

    # 4. Disclosure Lag
    disclosure_lag = {
        "median_days": "N/A",
        "late_pct": "N/A"
    }
    try:
        lags = []
        late_count = 0
        trades_with_dates = db.query(Trade).filter(Trade.trade_date.isnot(None), Trade.filing_date.isnot(None)).all()
        for t in trades_with_dates:
            diff = (t.filing_date - t.trade_date).days
            if diff >= 0:
                lags.append(diff)
                if diff > 45:
                    late_count += 1
        if lags:
            lags.sort()
            median = lags[len(lags) // 2]
            late_pct = int((late_count / len(lags)) * 100)
            disclosure_lag = {
                "median_days": str(median),
                "late_pct": f"{late_pct}%"
            }
    except Exception:
        pass

    # 5. Biggest Single Trade
    biggest_trade = None
    try:
        all_trades = db.query(Trade).all()
        max_val = -1.0
        best_t = None
        for t in all_trades:
            val_str = t.amount_range or ""
            clean = "".join(c for c in val_str.split("-")[-1] if c.isdigit())
            val = float(clean) if clean else 0
            if val > max_val:
                max_val = val
                best_t = t
                
        if best_t and max_val > 0:
            person = db.query(TargetPerson).filter(TargetPerson.id == best_t.target_person_id).first()
            if max_val >= 1000000:
                formatted_val = f"${max_val / 1000000:.1f}M"
            elif max_val >= 1000:
                formatted_val = f"${max_val / 1000:.0f}K"
            else:
                formatted_val = f"${max_val:.0f}"
                
            biggest_trade = {
                "amount": formatted_val,
                "person_name": person.name if person else "Unknown",
                "ticker": best_t.ticker,
                "date": best_t.trade_date.isoformat()
            }
    except Exception:
        pass
        
    if not biggest_trade:
        biggest_trade = {
            "amount": "N/A",
            "person_name": "No trades recorded",
            "ticker": "",
            "date": ""
        }

    return {
        "most_active": most_active,
        "biggest_outperformer": outperf,
        "hot_stock": hot_stock,
        "disclosure_lag": disclosure_lag,
        "biggest_trade": biggest_trade
    }
