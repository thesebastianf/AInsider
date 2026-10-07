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
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TargetPerson, Trade, Subscription
from app.services.fetcher import fetch_trades, RawTrade, fetch_wikipedia_photo
from app.services.llm_provider import evaluate_trade
from app.services.notifier import notify_all_enabled, notify_digest
from app.utils.names import normalize_person_name

logger = logging.getLogger("ainsider.pipeline")


def _get_or_create_person(db: Session, raw: RawTrade) -> TargetPerson:
    """Get existing person or create a new one."""
    from app.services.fetcher import FUND_MANAGER_MAPPING

    normalized_name = normalize_person_name(raw.person_name)
    raw.person_name = normalized_name
    person = db.query(TargetPerson).filter(TargetPerson.name == normalized_name).first()
    
    # Resolve display alias for funds (e.g. Scion Asset Management -> Scion Asset Management (Michael Burry))
    display_alias = None
    upper_name = normalized_name.upper()
    for fund_key, manager_name in FUND_MANAGER_MAPPING.items():
        if fund_key in upper_name:
            display_alias = f"{normalized_name} ({manager_name})"
            break

    if not person:
        person = TargetPerson(
            name=normalized_name,
            display_name=display_alias,
            category=raw.person_category,
            committee_affiliations=raw.committees,
            is_tracked=False,  # Auto-created persons from feed start as available (untracked)
            is_active=True,
        )
        db.add(person)
        db.flush()
        logger.info(f"Created available target person: {normalized_name} ({raw.person_category})")
    elif display_alias and not person.display_name:
        person.display_name = display_alias

    _maybe_fetch_photo(person)
    return person


# Photo lookups hit Wikipedia over the network. Feeds contain thousands of
# trades per run, so look each person up at most once per run and cap the
# total per run; persons not reached are picked up by the next run.
PHOTO_LOOKUPS_PER_RUN = 150
_photo_attempted: set[int] = set()
_photo_budget = PHOTO_LOOKUPS_PER_RUN


def _reset_photo_budget() -> None:
    global _photo_budget
    _photo_attempted.clear()
    _photo_budget = PHOTO_LOOKUPS_PER_RUN


def _maybe_fetch_photo(person: TargetPerson) -> None:
    global _photo_budget
    if person.photo_url or person.custom_photo_url or person.id in _photo_attempted:
        return
    if _photo_budget <= 0:
        return
    _photo_attempted.add(person.id)
    _photo_budget -= 1
    person.photo_url = fetch_wikipedia_photo(person.name)




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


def _dispatch_notifications(db: Session, pending: dict[int, tuple[str, list[dict]]]) -> int:
    """Send queued trade alerts: skip stale trades, digest bursts per person."""
    from app.config import settings
    from app.routers.system import add_log

    cutoff = date.today() - timedelta(days=settings.NOTIFY_MAX_AGE_DAYS)
    sent = 0
    for person_name, trades in pending.values():
        fresh = [t for t in trades if t["reference_date"] and t["reference_date"] >= cutoff]
        skipped = len(trades) - len(fresh)
        if skipped:
            add_log("INFO", f"Skipped {skipped} alert(s) for {person_name}: older than {settings.NOTIFY_MAX_AGE_DAYS} days")
        if not fresh:
            continue
        try:
            if len(fresh) > settings.NOTIFY_DIGEST_THRESHOLD:
                notify_digest(db, person_name, fresh)
                add_log("INFO", f"Sent digest alert for {person_name} ({len(fresh)} trades)")
            else:
                for t in fresh:
                    notify_all_enabled(
                        db=db,
                        person_name=person_name,
                        trade_type=t["trade_type"],
                        ticker=t["ticker"],
                        amount=t["amount"],
                        ai_score=t["ai_score"],
                        ai_summary=t["ai_summary"],
                        trade_date=t["trade_date"],
                    )
            sent += 1
        except Exception as e:
            logger.error(f"Notification failed for {person_name}: {e}")
            add_log("WARN", f"Notification error for {person_name}: {str(e)[:80]}")
    return sent


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

    if app.state.app_state.get("is_pipeline_running"):
        add_log("WARN", "Pipeline already running, skipping this trigger")
        return stats

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


        # Tracked persons get first claim on this run's photo lookups
        _reset_photo_budget()
        for person in db.query(TargetPerson).filter(
            TargetPerson.is_tracked == True,  # noqa: E712
            TargetPerson.photo_url.is_(None),
            TargetPerson.custom_photo_url.is_(None),
        ).all():
            _maybe_fetch_photo(person)
        db.commit()

        # ─── Pass 1: Fast Discovery ──────────────────────────────────
        # Create all TargetPersons instantly so the 'Discover' tab populates
        # immediately, before the 50+ minute yfinance rate-limited loop begins.
        for raw in raw_trades:
            _get_or_create_person(db, raw)
        db.commit()
        
        # ─── Pass 2: Trade Ingestion & Rate-Limited Lookups ──────────
        updated_tickers = set()
        pending_notifications: dict[int, tuple[str, list[dict]]] = {}
        subscribed_ids = {
            pid for (pid,) in db.query(Subscription.target_person_id)
            .filter(Subscription.user_id == "default").all()
        }

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

                # Step 6: Queue notification; dispatched after the loop so many
                # trades of one person in one run collapse into a single digest.
                if person.id in subscribed_ids:
                    pending_notifications.setdefault(person.id, (person.name, []))[1].append({
                        "trade_type": raw.trade_type,
                        "ticker": raw.ticker,
                        "amount": raw.amount_range,
                        "ai_score": trade.ai_score or 0,
                        "ai_summary": trade.ai_summary or "No AI evaluation",
                        "trade_date": raw.trade_date.isoformat() if raw.trade_date else "",
                        "reference_date": raw.filing_date or raw.trade_date,
                    })

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Pipeline error processing trade: {e}")
                add_log("ERROR", f"Pipeline error: {str(e)[:80]}")
                db.rollback()

        stats["notifications_sent"] = _dispatch_notifications(db, pending_notifications)

        try:
            from app.services.hot_alerts import check_hot_stock_entries
            check_hot_stock_entries(db)
        except Exception as e:
            logger.error(f"Hot stocks alert check failed: {e}")
            add_log("WARN", f"Hot stocks alert check failed: {str(e)[:80]}")

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
