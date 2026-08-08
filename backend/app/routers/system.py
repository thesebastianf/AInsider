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

    from app.models import DataSourceConfig
    
    # Get last pipeline run from max last_fetch across active sources
    last_run_val = db.query(func.max(DataSourceConfig.last_fetch)).filter(DataSourceConfig.is_enabled == True).scalar()
    
    # Get last price update from max last_updated
    last_price_val = db.query(func.max(AssetPerformance.last_updated)).scalar()

    last_run = last_run_val if last_run_val else None
    last_price = last_price_val if last_price_val else None

    # Fetch next run times from APScheduler instance
    next_pipeline = None
    next_price_update = None
    next_backup_run = None
    try:
        from app.tasks.scheduler import scheduler
        if scheduler.running:
            pipe_job = scheduler.get_job("pipeline_job")
            if pipe_job:
                next_pipeline = pipe_job.next_run_time
            price_job = scheduler.get_job("price_update_job")
            if price_job:
                next_price_update = price_job.next_run_time
            backup_job = scheduler.get_job("backup_job")
            if backup_job:
                next_backup_run = backup_job.next_run_time
    except Exception:
        pass

    return SystemStats(
        total_trades=total_trades,
        total_persons=total_persons,
        total_subscriptions=total_subscriptions,
        total_tickers=total_tickers,
        uptime_seconds=uptime_seconds,
        last_pipeline_run=last_run,
        is_pipeline_running=__import__("app.state", fromlist=["app_state"]).app_state.get("is_pipeline_running", False),
        next_pipeline_run=next_pipeline,
        last_price_update=last_price,
        next_price_update=next_price_update,
        next_backup_run=next_backup_run,
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

@router.post("/system/trigger-prices")
def trigger_price_update():
    """Manually trigger a yfinance price update."""
    from app.services.price_updater import update_all_prices
    try:
        add_log("INFO", "Manual price update trigger requested")
        update_all_prices()
        add_log("INFO", "Manual price update completed")
        return {"status": "success", "message": "Price update triggered successfully"}
    except Exception as e:
        add_log("ERROR", f"Price update error: {str(e)}")
        return {"status": "error", "message": str(e)}


def parse_amount_to_float(val_str: str) -> float:
    if not val_str:
        return 0.0
    val_str = val_str.strip()
    
    # Discard shares counts in parentheses
    if "(" in val_str:
        val_str = val_str.split("(")[0].strip()
        
    # Take upper range boundary if applicable
    if "-" in val_str:
        val_str = val_str.split("-")[-1].strip()
        
    val_str_upper = val_str.upper()
    multiplier = 1.0
    if "M" in val_str_upper:
        multiplier = 1_000_000.0
        val_str = val_str_upper.replace("M", "")
    elif "K" in val_str_upper:
        multiplier = 1_000.0
        val_str = val_str_upper.replace("K", "")
    elif "B" in val_str_upper:
        multiplier = 1_000_000_000.0
        val_str = val_str_upper.replace("B", "")
        
    cleaned_chars = []
    for c in val_str:
        if c.isdigit() or c == ".":
            cleaned_chars.append(c)
            
    cleaned_str = "".join(cleaned_chars)
    if not cleaned_str:
        return 0.0
    try:
        return float(cleaned_str) * multiplier
    except ValueError:
        return 0.0


@router.get("/system/insights")
def get_insights(db: Session = Depends(get_db)):
    """Calculate and return congressional trading platform insights."""
    from datetime import date, timedelta
    
    # 1. Most Active Tracked Persons
    most_active_list = []
    most_active = None
    try:
        active_q = (
            db.query(Trade.target_person_id, func.count(Trade.id).label("trade_count"))
            .group_by(Trade.target_person_id)
            .order_by(func.count(Trade.id).desc())
            .limit(3)
            .all()
        )
        for p_id, cnt in active_q:
            person = db.query(TargetPerson).filter(TargetPerson.id == p_id).first()
            if person:
                most_active_list.append({
                    "name": person.name,
                    "photo_url": person.custom_photo_url or person.photo_url,
                    "trades_count": cnt
                })
        if most_active_list:
            most_active = most_active_list[0]
    except Exception:
        pass

    if not most_active:
        most_active = {
            "name": "No trades recorded",
            "photo_url": None,
            "trades_count": 0
        }
    if not most_active_list:
        most_active_list = [most_active]

    # 2. Biggest Outperformer
    outperf_list = []
    outperf = None
    try:
        persons = db.query(TargetPerson).all()
        candidates = []
        for p in persons:
            tickers = [t[0] for t in db.query(Trade.ticker).filter(Trade.target_person_id == p.id).distinct().all()]
            if not tickers:
                continue
            perf_vals = db.query(AssetPerformance.ytd_performance_pct).filter(AssetPerformance.ticker.in_(tickers)).all()
            if perf_vals:
                valid_vals = [pv[0] for pv in perf_vals if pv[0] is not None]
                if valid_vals:
                    avg_perf = sum(valid_vals) / len(valid_vals)
                    candidates.append((avg_perf, p))
        candidates.sort(key=lambda x: -x[0])
        for avg_perf, p in candidates[:3]:
            outperf_list.append({
                "name": p.name,
                "photo_url": p.custom_photo_url or p.photo_url,
                "perf_vs_spy": f"+{avg_perf:.1f}% vs SPY" if avg_perf >= 0 else f"{avg_perf:.1f}% vs SPY"
            })
        if outperf_list:
            outperf = outperf_list[0]
    except Exception:
        pass
        
    if not outperf:
        outperf = {
            "name": "No trades recorded",
            "photo_url": None,
            "perf_vs_spy": "N/A"
        }
    if not outperf_list:
        outperf_list = [outperf]

    # 3. Hot Stock (60d)
    hot_stocks = []
    hot_stock = None
    try:
        from app.routers.trades import resolve_ticker_and_isin
        from sqlalchemy import case, distinct
        sixty_days_ago = date.today() - timedelta(days=60)
        INVALID_TICKERS = ["NONE", "NONE.", "N/A", "NA", "NULL", "UNKNOWN", ""]
        hot_q = (
            db.query(
                Trade.ticker,
                func.count(Trade.id).label("trade_count"),
                func.sum(case((Trade.type == "BUY", 1), else_=0)).label("buy_count"),
                func.sum(case((Trade.type == "SELL", 1), else_=0)).label("sell_count"),
                func.count(distinct(Trade.target_person_id)).label("distinct_persons"),
                func.max(Trade.trade_date).label("last_trade_date"),
            )
            .filter(
                Trade.trade_date >= sixty_days_ago,
                Trade.ticker.isnot(None),
                ~Trade.ticker.in_(INVALID_TICKERS)
            )
            .group_by(Trade.ticker)
            .order_by(func.count(Trade.id).desc())
            .limit(10)
            .all()
        )
        for row in hot_q:
            tick = row.ticker
            cnt = row.trade_count
            buy_cnt = int(row.buy_count or 0)
            sell_cnt = int(row.sell_count or 0)
            distinct_cnt = int(row.distinct_persons or 0)
            max_date = row.last_trade_date

            resolved_ticker, isin, company_name = resolve_ticker_and_isin(tick)
            ap = db.query(AssetPerformance).filter(AssetPerformance.ticker == tick).first()
            perf_pct = ap.ytd_performance_pct if ap else 0.0

            hot_stocks.append({
                "ticker": tick,
                "isin": isin,
                "company_name": company_name,
                "perf_pct": f"{perf_pct:+.1f}%" if perf_pct else "0.0%",
                "trades_count": cnt,
                "buy_count": buy_cnt,
                "sell_count": sell_cnt,
                "distinct_persons": distinct_cnt,
                "last_trade_date": max_date.isoformat() if max_date else None,
            })
        if hot_stocks:
            hot_stock = hot_stocks[0]
    except Exception as e:
        logger.error(f"Failed calculating hot stocks: {e}")
        
    if not hot_stock:
        hot_stock = {
            "ticker": "N/A",
            "isin": "",
            "company_name": "",
            "perf_pct": "N/A",
            "trades_count": 0,
            "buy_count": 0,
            "sell_count": 0,
            "distinct_persons": 0,
        }
    if not hot_stocks:
        hot_stocks = [hot_stock]

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

    # 5. Biggest Trades
    biggest_trades_list = []
    biggest_trade = None
    try:
        all_trades = db.query(Trade).all()
        candidates = []
        for t in all_trades:
            val = parse_amount_to_float(t.amount_range)
            if val > 0:
                candidates.append((val, t))
        candidates.sort(key=lambda x: -x[0])
        for val, t in candidates[:3]:
            person = db.query(TargetPerson).filter(TargetPerson.id == t.target_person_id).first()
            if val >= 1000000:
                formatted_val = f"${val / 1000000:.1f}M"
            elif val >= 1000:
                formatted_val = f"${val / 1000:.0f}K"
            else:
                formatted_val = f"${val:.0f}"
            biggest_trades_list.append({
                "amount": formatted_val,
                "person_name": person.name if person else "Unknown",
                "ticker": t.ticker,
                "date": t.trade_date.isoformat() if t.trade_date else ""
            })
        if biggest_trades_list:
            biggest_trade = biggest_trades_list[0]
    except Exception:
        pass
        
    if not biggest_trade:
        biggest_trade = {
            "amount": "N/A",
            "person_name": "No trades recorded",
            "ticker": "",
            "date": ""
        }
    if not biggest_trades_list:
        biggest_trades_list = [biggest_trade]

    return {
        "most_active": most_active,
        "most_active_list": most_active_list,
        "biggest_outperformer": outperf,
        "outperf_list": outperf_list,
        "hot_stock": hot_stock,
        "hot_stocks": hot_stocks,
        "disclosure_lag": disclosure_lag,
        "biggest_trade": biggest_trade,
        "biggest_trades_list": biggest_trades_list
    }
