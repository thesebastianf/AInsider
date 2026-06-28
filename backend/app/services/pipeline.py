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
        )
        db.add(person)
        db.flush()
        logger.info(f"Created new person: {raw.person_name} ({raw.person_category})")
    return person


def _insert_trade(db: Session, person: TargetPerson, raw: RawTrade) -> Trade | None:
    """Try to insert a trade, returns None if duplicate."""
    trade = Trade(
        target_person_id=person.id,
        ticker=raw.ticker,
        type=raw.trade_type,
        amount_range=raw.amount_range,
        trade_date=raw.trade_date,
        filing_date=raw.filing_date,
        source_url=raw.source_url,
    )
    db.add(trade)
    try:
        db.flush()
        return trade
    except IntegrityError:
        db.rollback()
        logger.debug(f"Duplicate trade skipped: {raw.person_name} {raw.ticker} {raw.trade_date}")
        return None


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
        # Step 1: Fetch trades
        raw_trades = fetch_trades()
        stats["fetched"] = len(raw_trades)
        add_log("INFO", f"Fetched {len(raw_trades)} raw trades")

        updated_tickers = set()

        for raw in raw_trades:
            try:
                # Step 2: Get or create person
                person = _get_or_create_person(db, raw)
                db.commit()

                # Step 3: Insert trade (deduplication)
                trade = _insert_trade(db, person, raw)
                if trade is None:
                    stats["duplicates"] += 1
                    continue

                stats["new_trades"] += 1
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

                    if person.is_followed or has_subs:
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
