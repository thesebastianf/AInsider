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
_FIXED_SLEEP_SEC = 2       # 2s fixed delay between ticker downloads to respect rate limits
_BACKOFF_DELAYS = [2, 6, 18] # Exponential backoff on 429
_PAUSE_HOURS = 2           # pause duration on circuit-breaker trip

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


def _make_intercepting_session():
    """
    Returns a curl_cffi Session that perfectly mimics Google Chrome to bypass 
    Yahoo's TLS fingerprinting, preventing 429 errors on the getcrumb endpoint.
    It also intercepts 429s as a fallback and implements a custom RequestsCookieJar
    wrapper to completely bypass bugs in curl_cffi's internal cookie handling.
    """
    from curl_cffi import requests as cffi_requests
    from requests.cookies import RequestsCookieJar
    from http.cookies import SimpleCookie
    
    class _429RaisingSession(cffi_requests.Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._my_cookie_jar = RequestsCookieJar()

        def request(self, method, url, **kwargs):
            # Extract cookies from our safe RequestsCookieJar
            cookie_dict = {}
            for cookie in self._my_cookie_jar:
                cookie_dict[cookie.name] = cookie.value
                
            # Merge with cookies passed in kwargs (if any)
            passed_cookies = kwargs.pop("cookies", None)
            if passed_cookies:
                if hasattr(passed_cookies, "items"):
                    cookie_dict.update(passed_cookies.items())
                else:
                    cookie_dict.update(passed_cookies)
                    
            kwargs["cookies"] = cookie_dict
            
            response = super().request(method, url, **kwargs)
            if response.status_code == 429:
                raise RuntimeError(
                    f"YAHOO_429: rate limited on {url[:80]}"
                )
            
            # Extract cookies from response headers to avoid curl_cffi CookieConflict
            for header, val in response.headers.items():
                if header.lower() == "set-cookie":
                    try:
                        c = SimpleCookie()
                        c.load(val)
                        for name, morsel in c.items():
                            self._my_cookie_jar.set(name, morsel.value)
                    except Exception:
                        pass
            
            response.cookies = self._my_cookie_jar
            return response

        @property
        def cookies(self):
            return self._my_cookie_jar

        @cookies.setter
        def cookies(self, val):
            if val is not None:
                self._my_cookie_jar = val

    # Use impersonation which bypasses Yahoo TLS fingerprinting blocks
    session = _429RaisingSession(impersonate="chrome")
    
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    })
    return session


def _download_single(ticker: str, session: requests.Session) -> pd.Series:
    """
    Download 5y daily Close prices for a single ticker.
    """
    try:
        # Pass our intercepting session so 429s raise immediately
        data = yf.download(
            ticker,
            period="5y",
            progress=False,
            auto_adjust=False,
            threads=False,
            session=session,
        )
        if data.empty:
            return pd.Series(dtype=float)

        # MultiIndex or single index columns
        if isinstance(data.columns, pd.MultiIndex):
            if "Close" in data.columns.get_level_values(0):
                close = data["Close"].iloc[:, 0]
            else:
                return pd.Series(dtype=float)
        else:
            if "Close" in data.columns:
                close = data["Close"]
            else:
                return pd.Series(dtype=float)

        # Normalize index (drop tz info, keep date only)
        if hasattr(close.index, "tz") and close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        close.index = close.index.normalize()
        return close.dropna()

    except RuntimeError as e:
        if "YAHOO_429" in str(e):
            raise  # let caller handle it
        logger.error(f"Unexpected error downloading ticker {ticker}: {e}")
        return pd.Series(dtype=float)
    except Exception as e:
        logger.error(f"yf.download error for {ticker}: {e}")
        return pd.Series(dtype=float)


def update_all_prices() -> None:
    """
    Main entry point. Batch-fetches prices for all tickers of
    tracked/followed persons and backfills price_at_transaction.
    """
    global _consecutive_chunk_failures

    # Clear stale cookie cache from database on startup to wipe out the string cookies
    try:
        from yfinance import cache
        cache.get_cookie_cache().store('basic', None)
        cache.get_cookie_cache().store('csrf', None)
        logger.info("Cleared yfinance persistent cookie cache.")
    except Exception as e:
        logger.debug(f"Failed to clear yfinance cookie cache: {e}")

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
            f"Processing individually with {_FIXED_SLEEP_SEC}s delay."
        )

        if not tickers:
            logger.info("All tickers already updated today.")
            return

        year_start = pd.Timestamp(date(date.today().year, 1, 1))
        session = _make_intercepting_session()
        total_updated = 0

        # ── 3. Process individually ───────────────────────────────────────────
        for idx, ticker in enumerate(tickers):
            if _is_rate_limited():
                logger.info("Circuit-breaker active mid-run. Stopping.")
                break

            logger.info(f"Ticker {idx + 1}/{len(tickers)}: downloading {ticker}...")

            s = pd.Series(dtype=float)
            success = False
            
            for attempt, delay in enumerate(_BACKOFF_DELAYS):
                try:
                    s = _download_single(ticker, session)
                    success = True
                    break # Success
                except RuntimeError as e:
                    if "YAHOO_429" in str(e):
                        logger.warning(f"Yahoo 429 on {ticker} (attempt {attempt+1}), backing off for {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Error for {ticker}: {e}")
                        break
                except Exception as e:
                    logger.error(f"Error for {ticker}: {e}")
                    break
                    
            if not success:
                logger.error(f"Exhausted backoff for {ticker}. Tripping circuit breaker.")
                _trip_circuit_breaker(db)
                break

            with _state_lock:
                _consecutive_chunk_failures = 0

            # ── 4. Process the downloaded series ─────────────────
            try:
                if s.empty:
                    # Still fixed 2s delay after even if empty, to respect rate limits
                    time.sleep(_FIXED_SLEEP_SEC)
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
            logger.info(f"Processed {ticker}. Total so far: {total_updated}")

            # Sleep between tickers
            if idx < len(tickers) - 1:
                logger.debug(f"Sleeping {_FIXED_SLEEP_SEC}s before next ticker…")
                time.sleep(_FIXED_SLEEP_SEC)

        logger.info(
            f"Price update complete. Updated: {total_updated}/{len(tickers)} tickers."
        )

    except Exception as e:
        logger.error(f"Price update run failed: {e}")
        db.rollback()
    finally:
        db.close()