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
from app.services.fetcher import fetch_trades, RawTrade, fetch_wikipedia_photo
from app.services.llm_provider import evaluate_trade

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
            photo_url=fetch_wikipedia_photo(raw.person_name),
            is_tracked=False,  # Auto-created persons from feed start as available (untracked)
            is_active=True,
        )
        db.add(person)
        db.flush()
        logger.info(f"Created available target person: {raw.person_name} ({raw.person_category})")
    return person




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
    import app.state

    stats = {
        "fetched": 0, "new_trades": 0, "duplicates": 0,
        "ai_evaluated": 0, "prices_updated": 0,
        "notifications_sent": 0, "errors": 0,
    }

    add_log("INFO", "═══ Pipeline started ═══")
    logger.info("Pipeline run started")

    db = SessionLocal()
    app.state.app_state["is_pipeline_running"] = True
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

        # Step 1b: Pre-fetch historical prices for all unique tickers
        # that are not already fully cached. This prevents N individual HTTP
        # calls inside the main loop and dramatically reduces rate-limit exposure.
        global _price_cache
        _price_cache = {}  # Reset cache each pipeline run


        # ─── Pass 1: Fast Discovery ──────────────────────────────────
        # Create all TargetPersons instantly so the 'Discover' tab populates
        # immediately, before the 50+ minute yfinance rate-limited loop begins.
        for raw in raw_trades:
            _get_or_create_person(db, raw)
        db.commit()
        
        # ─── Pass 2: Trade Ingestion & Rate-Limited Lookups ──────────
        updated_tickers = set()

        for raw in raw_trades:
            try:
                # Get the person (already created in Pass 1)
                person = db.query(TargetPerson).filter(TargetPerson.name == raw.person_name).first()
                if not person:
                    continue

                # Step 3: Insert trade (deduplication)
                # First check if we need to fetch price
                existing = db.query(Trade).filter(
                    Trade.target_person_id == person.id,
                    Trade.ticker == raw.ticker,
                    Trade.trade_date == raw.trade_date,
                    Trade.amount_range == raw.amount_range,
                ).first()
                if existing:
                    stats["duplicates"] += 1
                    continue
                    
                # New trade, resolve price using transaction price from raw feed
                trade = _insert_trade(db, person, raw, price_at_transaction=raw.price_at_transaction)
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

                # Step 5: Price update is now batched at the end of the pipeline
                if raw.ticker not in updated_tickers:
                    updated_tickers.add(raw.ticker)
                    stats["prices_updated"] += 1

                # Step 6: Notifications to all enabled providers
                try:
                    subscription = db.query(Subscription).filter(Subscription.target_person_id == person.id).first()
                    if subscription:
                        notify_all_enabled(
                            db=db,
                            person_name=person.name,
                            trade_type=raw.trade_type,
                            ticker=raw.ticker,
                            amount=raw.amount_range,
                            ai_score=trade.ai_score or 0,
                            ai_summary=trade.ai_summary or "No AI evaluation",
                            trade_date=raw.trade_date.isoformat() if raw.trade_date else "",
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
        app.state.app_state["is_pipeline_running"] = False
        db.close()

    return stats
