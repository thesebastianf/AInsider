"""
AInsider Tracker – Stock Price Updater

API Call Strategy (minimized):
  - Uses yf.download() in chunks of up to 200 tickers per HTTP call
  - For 1500 symbols: ~8 HTTP calls total (vs. 1500 with per-ticker approach)
  - Skips tickers already updated today → further reduces calls on re-runs
  - Sleeps 20s between chunks to stay safely under rate limits

429 Circuit-Breaker:
  - A custom requests.Session intercepts every HTTP response.
  - On first 429 it raises immediately, stopping yfinance's internal retry loop.
  - After 2 consecutive chunk failures → 1h pause + exactly ONE push notification.
  - During a pause window, update_all_prices() exits immediately (zero yfinance calls).
"""

import logging
import time
import threading
from datetime import datetime, date, timedelta

import requests
import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session

from app.models import AssetPerformance, Trade
from app.database import SessionLocal

logger = logging.getLogger("ainsider.price_updater")

# ── Config ─────────────────────────────────────────────────────────────────────
_CHUNK_SIZE = 200          # tickers per yf.download call
_INTER_CHUNK_SLEEP = 20    # seconds between chunks (respectful rate)
_PAUSE_HOURS = 1           # pause duration on circuit-breaker trip
_MAX_CHUNK_FAILURES = 2    # consecutive empty-chunk failures before pause

# ── Circuit-breaker state (in-process, resets on container restart) ────────────
_state_lock = threading.Lock()
_rate_limit_until: datetime | None = None
_consecutive_chunk_failures: int = 0
_notification_sent_until: datetime | None = None  # prevents repeat notifications


def _is_rate_limited() -> bool:
    with _state_lock:
        global _rate_limit_until
        if _rate_limit_until and datetime.now() < _rate_limit_until:
            return True
        if _rate_limit_until and datetime.now() >= _rate_limit_until:
            _rate_limit_until = None  # pause expired, reset
        return False


def _trip_circuit_breaker(db: Session) -> None:
    """Activate pause and send exactly ONE notification (suppressed for 1h)."""
    global _rate_limit_until, _consecutive_chunk_failures, _notification_sent_until
    with _state_lock:
        _rate_limit_until = datetime.now() + timedelta(hours=_PAUSE_HOURS)
        _consecutive_chunk_failures = 0
        resume_str = _rate_limit_until.strftime("%H:%M")

        # Only send notification if we haven't sent one recently
        now = datetime.now()
        should_notify = (
            _notification_sent_until is None or now >= _notification_sent_until
        )
        if should_notify:
            _notification_sent_until = now + timedelta(hours=_PAUSE_HOURS)

    logger.error(
        f"Yahoo Finance rate limit circuit-breaker tripped. "
        f"All price updates paused until {resume_str}."
    )
    if should_notify:
        try:
            from app.services.notifier import notify_system_event
            notify_system_event(
                db,
                "⚠️ Yahoo Finance Rate Limit",
                f"AInsider hit Yahoo Finance rate limits (429).\n"
                f"Background price updates are paused until {resume_str}.\n"
                f"No further alerts will be sent during this pause window.",
            )
        except Exception as e:
            logger.error(f"Failed to send rate-limit notification: {e}")


def _make_intercepting_session() -> requests.Session:
    """
    Returns a requests.Session that raises immediately on HTTP 429,
    preventing yfinance from its internal retry-and-toggle loop.
    """
    class _429RaisingSession(requests.Session):
        def send(self, prepared_request, **kwargs):
            response = super().send(prepared_request, **kwargs)
            if response.status_code == 429:
                raise RuntimeError(
                    f"YAHOO_429: rate limited on {prepared_request.url[:80]}"
                )
            return response

    session = _429RaisingSession()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    })
    return session


def _download_chunk(tickers: list[str], session: requests.Session) -> pd.DataFrame:
    """
    Download 5y daily Close prices for a chunk of tickers.
    Uses yf.download() – one HTTP call for the whole chunk.
    Returns a DataFrame with columns = ticker symbols, or empty on failure.
    """
    ticker_str = " ".join(tickers)
    try:
        # Pass our intercepting session so 429s raise immediately
        data = yf.download(
            ticker_str,
            period="5y",
            progress=False,
            auto_adjust=False,
            session=session,
        )
        if data.empty:
            return pd.DataFrame()

        # Multi-ticker download has MultiIndex columns; normalize to just Close
        if isinstance(data.columns, pd.MultiIndex):
            if "Close" in data.columns.get_level_values(0):
                close = data["Close"]
            else:
                return pd.DataFrame()
        else:
            # Single ticker: columns are Open/High/Low/Close/Volume
            if "Close" in data.columns:
                close = data[["Close"]].rename(columns={"Close": tickers[0]})
            else:
                return pd.DataFrame()

        # Normalize index (drop tz info, keep date only)
        if hasattr(close.index, "tz") and close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        close.index = close.index.normalize()
        return close

    except RuntimeError as e:
        if "YAHOO_429" in str(e):
            raise  # let caller handle it
        logger.error(f"Unexpected error downloading chunk: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"yf.download error: {e}")
        return pd.DataFrame()


def update_all_prices() -> None:
    """
    Main entry point. Batch-fetches prices for all tickers of
    tracked/followed persons and backfills price_at_transaction.
    """
    global _consecutive_chunk_failures

    if _is_rate_limited():
        resume = _rate_limit_until.strftime("%H:%M") if _rate_limit_until else "?"
        logger.info(f"Price update skipped – rate limit pause active until {resume}.")
        return

    db = SessionLocal()
    try:
        from app.models import TargetPerson

        # ── 1. Collect unique tickers (tracked/followed persons only) ──────────
        all_tickers: list[str] = [
            row[0] for row in
            db.query(Trade.ticker)
            .join(TargetPerson, Trade.target_person_id == TargetPerson.id)
            .filter(
                (TargetPerson.is_tracked == True) | (TargetPerson.is_followed == True)
            )
            .distinct()
            .all()
        ]

        if not all_tickers:
            logger.info("No active tickers to update.")
            return

        # ── 2. Skip tickers already updated today (reduces re-run calls) ──────
        today = datetime.now().date()
        already_fresh = {
            row[0] for row in
            db.query(AssetPerformance.ticker, AssetPerformance.last_updated)
            .filter(AssetPerformance.last_updated >= datetime(today.year, today.month, today.day))
            .all()
        }
        tickers = [t for t in all_tickers if t not in already_fresh]
        skipped_fresh = len(all_tickers) - len(tickers)

        logger.info(
            f"Price update: {len(tickers)} tickers to update "
            f"({skipped_fresh} already fresh today, {len(all_tickers)} total). "
            f"Chunks of {_CHUNK_SIZE} = {max(1, -(-len(tickers) // _CHUNK_SIZE))} API calls."
        )

        if not tickers:
            logger.info("All tickers already updated today.")
            return

        year_start = pd.Timestamp(date(date.today().year, 1, 1))
        session = _make_intercepting_session()
        total_updated = 0

        # ── 3. Process in chunks ───────────────────────────────────────────────
        chunks = [tickers[i:i + _CHUNK_SIZE] for i in range(0, len(tickers), _CHUNK_SIZE)]

        for chunk_idx, chunk in enumerate(chunks):
            if _is_rate_limited():
                logger.info("Circuit-breaker active mid-run. Stopping.")
                break

            logger.info(
                f"Chunk {chunk_idx + 1}/{len(chunks)}: "
                f"downloading {len(chunk)} tickers..."
            )

            try:
                close_df = _download_chunk(chunk, session)
            except RuntimeError as e:
                if "YAHOO_429" in str(e):
                    with _state_lock:
                        _consecutive_chunk_failures += 1
                        failures = _consecutive_chunk_failures
                    logger.warning(
                        f"429 on chunk {chunk_idx + 1} "
                        f"(consecutive failures: {failures})"
                    )
                    if failures >= _MAX_CHUNK_FAILURES:
                        _trip_circuit_breaker(db)
                        break
                    # One failure: sleep longer and retry
                    logger.info(f"Sleeping 60s before next chunk...")
                    time.sleep(60)
                    continue
                else:
                    logger.error(f"Chunk {chunk_idx + 1} error: {e}")
                    continue

            # Empty result = likely rate limited or all tickers invalid
            if close_df.empty:
                with _state_lock:
                    _consecutive_chunk_failures += 1
                    failures = _consecutive_chunk_failures
                logger.warning(
                    f"Empty result for chunk {chunk_idx + 1} "
                    f"(consecutive failures: {failures})"
                )
                if failures >= _MAX_CHUNK_FAILURES:
                    _trip_circuit_breaker(db)
                    break
                time.sleep(60)
                continue

            # Successful chunk → reset failure counter
            with _state_lock:
                _consecutive_chunk_failures = 0

            # ── 4. Process each ticker in the downloaded chunk ─────────────────
            for ticker in chunk:
                try:
                    # Extract series for this ticker
                    if ticker in close_df.columns:
                        s = close_df[ticker].dropna()
                    elif len(chunk) == 1 and not close_df.empty:
                        s = close_df.iloc[:, 0].dropna()
                    else:
                        continue

                    if s.empty:
                        continue

                    current_price = float(s.iloc[-1])

                    # YTD performance
                    ytd_pct = None
                    ytd_s = s.loc[year_start:]
                    if not ytd_s.empty:
                        start_p = float(ytd_s.iloc[0])
                        if start_p > 0:
                            ytd_pct = round(
                                ((current_price - start_p) / start_p) * 100, 2
                            )

                    # Upsert AssetPerformance
                    asset = (
                        db.query(AssetPerformance)
                        .filter(AssetPerformance.ticker == ticker)
                        .first()
                    )
                    if asset:
                        asset.current_price = round(current_price, 2)
                        asset.ytd_performance_pct = ytd_pct
                        asset.last_updated = datetime.now()
                    else:
                        db.add(AssetPerformance(
                            ticker=ticker,
                            current_price=round(current_price, 2),
                            ytd_performance_pct=ytd_pct,
                            last_updated=datetime.now(),
                        ))

                    # Backfill missing price_at_transaction
                    missing = (
                        db.query(Trade)
                        .join(TargetPerson, Trade.target_person_id == TargetPerson.id)
                        .filter(
                            Trade.ticker == ticker,
                            Trade.price_at_transaction == None,
                            (TargetPerson.is_tracked == True) | (TargetPerson.is_followed == True),
                        )
                        .all()
                    )
                    backfilled = 0
                    for trade in missing:
                        if not trade.trade_date:
                            continue
                        t_date = pd.Timestamp(trade.trade_date).normalize()
                        for offset in range(7):
                            check = t_date + pd.Timedelta(days=offset)
                            if check in s.index:
                                trade.price_at_transaction = float(s.loc[check])
                                backfilled += 1
                                break

                    total_updated += 1
                    if backfilled:
                        logger.debug(
                            f"{ticker}: ${current_price:.2f} YTD:{ytd_pct}% "
                            f"backfilled:{backfilled}"
                        )

                except Exception as e:
                    logger.error(f"Processing {ticker} failed: {e}")

            db.commit()
            logger.info(
                f"Chunk {chunk_idx + 1}/{len(chunks)} done "
                f"(+{len(chunk)} tickers). Total so far: {total_updated}"
            )

            # Sleep between chunks (not after the last one)
            if chunk_idx < len(chunks) - 1:
                logger.debug(f"Sleeping {_INTER_CHUNK_SLEEP}s before next chunk…")
                time.sleep(_INTER_CHUNK_SLEEP)

        logger.info(
            f"Price update complete. Updated: {total_updated}/{len(tickers)} tickers."
        )

    except Exception as e:
        logger.error(f"Price update run failed: {e}")
        db.rollback()
    finally:
        db.close()