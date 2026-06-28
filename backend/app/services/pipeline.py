"""
AInsider Tracker – Data Pipeline
Orchestrates the complete trade ingestion pipeline:
  1. Fetch new trades
  2. Deduplicate against DB
  3. AI evaluation via configured LLM provider
  4. Price update via yfinance
  5. Notification dispatch to all enabled providers
"""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TargetPerson, Trade, Subscription
from app.services.fetcher import fetch_trades, RawTrade
from app.services.llm_provider import evaluate_trade
from app.services.price_updater import update_ticker_price
from app.services.notifier import notify_all_enabled

logger = logging.getLogger("ainsider.pipeline")


def _get_or_create_person(db: Session, raw: RawTrade) -> TargetPerson:
    """Get existing person or create a new one."""
    person = db.query(TargetPerson).filter(TargetPerson.name == raw.person_name).first()
    if not person:
        person = TargetPerson(
            name=raw.person_name,
            category=raw.person_category,
            committee_affiliations=raw.committees,
            is_tracked=False,  # Auto-created persons from feed start as available (untracked)
            is_active=True,
        )
        db.add(person)
        db.flush()
        logger.info(f"Created available target person: {raw.person_name} ({raw.person_category})")
    return person


# In-memory price cache for the current pipeline run: (ticker, date_str) -> price
_price_cache: dict = {}


def _get_historical_price(ticker: str, trade_date, *, _delay: float = 2.0, _retries: int = 3) -> float | None:
    """Fetch the close price of a ticker on a specific trade date.
    
    Results are cached per (ticker, date) within the pipeline run to avoid
    duplicate yfinance calls. Uses exponential backoff on rate-limit errors.
    """
    import yfinance as yf
    from datetime import timedelta
    import time

    cache_key = (ticker, trade_date.isoformat())
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    for attempt in range(_retries):
        try:
            time.sleep(_delay)  # Fixed delay between calls to stay within free tier
            stock = yf.Ticker(ticker)
            start_str = trade_date.isoformat()
            end_date = trade_date + timedelta(days=5)
            hist = stock.history(start=start_str, end=end_date.isoformat())
            if not hist.empty:
                price = float(hist["Close"].iloc[0])
                _price_cache[cache_key] = price
                return price
            # No data for this date window (e.g. delisted ticker)
            _price_cache[cache_key] = None
            return None
        except Exception as e:
            err_str = str(e)
            if "Too Many Requests" in err_str or "Rate limited" in err_str:
                wait = _delay * (3 ** attempt)  # Exponential backoff: 2s, 6s, 18s
                logger.warning(
                    f"Rate limited fetching {ticker} on {trade_date} "
                    f"(attempt {attempt + 1}/{_retries}), waiting {wait:.0f}s..."
                )
                time.sleep(wait)
            else:
                logger.warning(f"Failed to fetch historical price for {ticker} on {trade_date}: {e}")
                _price_cache[cache_key] = None
                return None

    logger.warning(f"Gave up fetching price for {ticker} on {trade_date} after {_retries} retries")
    _price_cache[cache_key] = None
    return None


def _insert_trade(db: Session, person: TargetPerson, raw: RawTrade, price_at_transaction: float | None = None) -> Trade | None:
    """Try to insert a trade, returns None if duplicate."""
    existing = db.query(Trade).filter(
        Trade.target_person_id == person.id,
        Trade.ticker == raw.ticker,
        Trade.trade_date == raw.trade_date,
        Trade.amount_range == raw.amount_range,
    ).first()
    if existing:
        return None

    trade = Trade(
        target_person_id=person.id,
        ticker=raw.ticker,
        type=raw.trade_type,
        amount_range=raw.amount_range,
        trade_date=raw.trade_date,
        filing_date=raw.filing_date,
        source_url=raw.source_url,
        price_at_transaction=price_at_transaction,
    )
    db.add(trade)
    try:
        db.flush()
        return trade
    except IntegrityError:
        db.rollback()
        logger.debug(f"Duplicate trade skipped: {raw.person_name} {raw.ticker} {raw.trade_date}")
        return None


def refresh_person_activity(db: Session) -> int:
    """Mark target persons with no trades in the last 365 days as inactive."""
    from datetime import date, timedelta
    cutoff_date = date.today() - timedelta(days=365)
    
    inactive_count = 0
    active_persons = db.query(TargetPerson).filter(TargetPerson.is_active == True).all()
    
    for person in active_persons:
        latest_trade = db.query(Trade).filter(Trade.target_person_id == person.id).order_by(Trade.trade_date.desc()).first()
        if latest_trade and latest_trade.trade_date < cutoff_date:
            person.is_active = False
            inactive_count += 1
            logger.info(f"Marked target person inactive (no trades in 365d): {person.name}")
        elif not latest_trade and person.created_at and (date.today() - person.created_at.date()) > timedelta(days=365):
            person.is_active = False
            inactive_count += 1
            logger.info(f"Marked target person inactive (no trades ever and created >365d ago): {person.name}")
            
    if inactive_count > 0:
        db.commit()
    return inactive_count


def run_pipeline() -> dict:
    """Execute the complete data pipeline."""
    from app.routers.system import add_log
    from app.routers.settings import _runtime_overrides

    stats = {
        "fetched": 0, "new_trades": 0, "duplicates": 0,
        "ai_evaluated": 0, "prices_updated": 0,
        "notifications_sent": 0, "errors": 0,
    }

    add_log("INFO", "═══ Pipeline started ═══")
    logger.info("Pipeline run started")

    db = SessionLocal()
    try:
        # Run daily activity cleanup
        try:
            inactive_count = refresh_person_activity(db)
            if inactive_count > 0:
                add_log("INFO", f"Marked {inactive_count} target persons as inactive due to no recent trades")
        except Exception as e:
            logger.error(f"Failed to refresh person activity: {e}")

        # Step 1: Fetch trades
        raw_trades = fetch_trades()
        stats["fetched"] = len(raw_trades)
        add_log("INFO", f"Fetched {len(raw_trades)} raw trades")

        # Step 1b: Pre-fetch historical prices for all unique (ticker, date) pairs
        # that are not already in the DB or cache – this prevents N individual HTTP
        # calls inside the main loop and dramatically reduces rate-limit exposure.
        global _price_cache
        _price_cache = {}  # Reset cache each pipeline run

        unique_pairs = set()
        for raw in raw_trades:
            unique_pairs.add((raw.ticker, raw.trade_date))
        
        add_log("INFO", f"Pre-fetching historical prices for {len(unique_pairs)} unique (ticker, date) pairs...")
        for ticker, trade_date in unique_pairs:
            # Skip if already in DB (existing trade with price already captured)
            existing_price = db.query(Trade.price_at_transaction).filter(
                Trade.ticker == ticker,
                Trade.trade_date == trade_date,
                Trade.price_at_transaction.isnot(None),
            ).first()
            if existing_price:
                _price_cache[(ticker, trade_date.isoformat())] = existing_price[0]
            else:
                _get_historical_price(ticker, trade_date)  # Result goes into _price_cache
        
        add_log("INFO", "Historical price pre-fetch complete")

        updated_tickers = set()

        for raw in raw_trades:
            try:
                # Step 2: Get or create person
                person = _get_or_create_person(db, raw)
                db.commit()

                # Step 3: Insert trade (deduplication) — pass cached price
                cached_price = _price_cache.get((raw.ticker, raw.trade_date.isoformat()))
                trade = _insert_trade(db, person, raw, price_at_transaction=cached_price)
                if trade is None:
                    stats["duplicates"] += 1
                    continue

                stats["new_trades"] += 1

                # If the person is not actively tracked, skip downstream AI, price updates, and notifications
                if not person.is_tracked:
                    db.commit()
                    continue

                add_log("INFO", f"New trade: {raw.person_name} {raw.trade_type} {raw.ticker} ({raw.amount_range})")

                # Step 4: AI Evaluation via configured LLM provider
                try:
                    score, summary = evaluate_trade(
                        db=db,
                        person_name=person.name,
                        committees=person.committee_affiliations or [],
                        trade_type=raw.trade_type,
                        ticker=raw.ticker,
                        amount=raw.amount_range,
                    )
                    trade.ai_score = score
                    trade.ai_summary = summary
                    stats["ai_evaluated"] += 1
                    add_log("INFO", f"AI evaluated {raw.ticker}: Score {score}/10")
                except Exception as e:
                    logger.error(f"AI evaluation failed for {raw.ticker}: {e}")
                    trade.ai_score = 0
                    trade.ai_summary = "AI evaluation failed"
                    add_log("WARN", f"AI evaluation failed for {raw.ticker}: {str(e)[:50]}")

                db.commit()

                # Step 5: Price update (only once per ticker)
                if raw.ticker not in updated_tickers:
                    try:
                        update_ticker_price(raw.ticker, db)
                        updated_tickers.add(raw.ticker)
                        stats["prices_updated"] += 1
                    except Exception as e:
                        logger.error(f"Price update failed for {raw.ticker}: {e}")
                        add_log("WARN", f"Price update failed for {raw.ticker}")

                # Step 6: Notifications to all enabled providers
                try:
                    # Check if person is followed or has subscriptions
                    has_subs = db.query(Subscription).filter(
                        Subscription.target_person_id == person.id
                    ).count() > 0

                    if has_subs:
                        notify_all_enabled(
                            db=db,
                            person_name=person.name,
                            trade_type=trade.type,
                            ticker=trade.ticker,
                            amount=trade.amount_range,
                            ai_score=trade.ai_score or 0,
                            ai_summary=trade.ai_summary or "No AI evaluation",
                        )
                        stats["notifications_sent"] += 1
                except Exception as e:
                    logger.error(f"Notification failed: {e}")
                    add_log("WARN", f"Notification error: {str(e)[:50]}")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Pipeline error processing trade: {e}")
                add_log("ERROR", f"Pipeline error: {str(e)[:80]}")
                db.rollback()

        _runtime_overrides["last_pipeline_run"] = datetime.now()

        summary_msg = (
            f"Pipeline complete: {stats['new_trades']} new, "
            f"{stats['duplicates']} duplicates, "
            f"{stats['ai_evaluated']} AI evaluated, "
            f"{stats['errors']} errors"
        )
        add_log("INFO", summary_msg)
        logger.info(summary_msg)

    except Exception as e:
        logger.error(f"Pipeline fatal error: {e}")
        add_log("ERROR", f"Pipeline fatal error: {str(e)[:100]}")
        stats["errors"] += 1
    finally:
        db.close()

    return stats
