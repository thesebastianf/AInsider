"""
AInsider Tracker – Stock Price Updater
Fetches current stock prices and YTD performance using yfinance.
"""

import logging
import time
from datetime import datetime, date

import yfinance as yf
from sqlalchemy.orm import Session

from app.models import AssetPerformance, Trade
from app.database import SessionLocal

logger = logging.getLogger("ainsider.price_updater")

# Rate limiting: track last request time
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 1.0  # seconds between requests


def _rate_limit():
    """Ensure minimum interval between yfinance requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def update_ticker_price(ticker: str, db: Session) -> None:
    """Fetch and update price data for a single ticker."""
    try:
        _rate_limit()
        stock = yf.Ticker(ticker)

        # Get current price
        current_price = None
        try:
            info = stock.info
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        except Exception:
            pass

        # Fallback: use last close from history
        if current_price is None:
            try:
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])
            except Exception:
                pass

        if current_price is None:
            logger.warning(f"Could not fetch price for {ticker}")
            return

        # Calculate YTD performance
        ytd_pct = None
        try:
            year_start = date(date.today().year, 1, 1)
            hist_ytd = stock.history(start=year_start.isoformat(), end=date.today().isoformat())
            if not hist_ytd.empty and len(hist_ytd) > 1:
                start_price = float(hist_ytd["Close"].iloc[0])
                if start_price > 0:
                    ytd_pct = round(((current_price - start_price) / start_price) * 100, 2)
        except Exception as e:
            logger.debug(f"Could not calculate YTD for {ticker}: {e}")

        # Upsert into asset_performance
        asset = db.query(AssetPerformance).filter(AssetPerformance.ticker == ticker).first()
        if asset:
            asset.current_price = round(current_price, 2)
            asset.ytd_performance_pct = ytd_pct
            asset.last_updated = datetime.now()
        else:
            asset = AssetPerformance(
                ticker=ticker,
                current_price=round(current_price, 2),
                ytd_performance_pct=ytd_pct,
                last_updated=datetime.now(),
            )
            db.add(asset)

        db.commit()
        logger.info(f"Updated {ticker}: ${current_price:.2f}, YTD: {ytd_pct}%")

    except Exception as e:
        logger.error(f"Failed to update price for {ticker}: {e}")
        db.rollback()



def update_all_prices() -> None:
    """Update prices and backfill missing Trade.price_at_transaction for active tickers in batch."""
    db = SessionLocal()
    try:
        from app.models import TargetPerson, Trade
        import yfinance as yf
        import pandas as pd
        from datetime import date, datetime, timedelta
        from app.routers.settings import _runtime_overrides
        from app.services.notifier import notify_system_event

        # Check rate limit pause
        rate_limit_until = _runtime_overrides.get("rate_limit_until")
        if rate_limit_until and datetime.now() < rate_limit_until:
            logger.info(f"Skipping price updates due to rate limit pause until {rate_limit_until}")
            return
            
        # Get unique tickers from trades belonging to tracked or followed persons
        tickers = [
            row[0] for row in db.query(Trade.ticker)
            .join(TargetPerson, Trade.target_person_id == TargetPerson.id)
            .filter((TargetPerson.is_tracked == True) | (TargetPerson.is_followed == True))
            .distinct().all()
        ]
        
        if not tickers:
            logger.info("No active tracked/followed tickers to update.")
            return

        logger.info(f"Batch updating prices for {len(tickers)} active tickers")

        year_start = date(date.today().year, 1, 1)
        
        chunk_size = 50
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            if not chunk: continue
            
            try:
                # Fetch 5y history to ensure we can backfill most historical trades
                data = yf.download(chunk, period="5y", progress=False, auto_adjust=False)
                if data.empty or 'Close' not in data:
                    continue
                    
                close_data = data['Close']
                # Normalize index to avoid tz issues during lookup
                if hasattr(close_data.index, 'tz_localize'):
                    close_data.index = close_data.index.tz_localize(None).normalize()
                
                for ticker in chunk:
                    try:
                        if len(chunk) == 1:
                            s = close_data.dropna()
                        else:
                            if ticker not in close_data: continue
                            s = close_data[ticker].dropna()
                            
                        if s.empty: continue
                        
                        current_price = float(s.iloc[-1])
                        
                        # Calculate YTD from this series
                        ytd_pct = None
                        year_start_ts = pd.Timestamp(year_start)
                        # Find closest date to year start
                        ytd_series = s.loc[year_start_ts:]
                        if not ytd_series.empty:
                            start_price = float(ytd_series.iloc[0])
                            if start_price > 0:
                                ytd_pct = round(((current_price - start_price) / start_price) * 100, 2)
                            
                        # Upsert into asset_performance
                        asset = db.query(AssetPerformance).filter(AssetPerformance.ticker == ticker).first()
                        if asset:
                            asset.current_price = round(current_price, 2)
                            asset.ytd_performance_pct = ytd_pct
                            asset.last_updated = datetime.now()
                        else:
                            asset = AssetPerformance(
                                ticker=ticker,
                                current_price=round(current_price, 2),
                                ytd_performance_pct=ytd_pct,
                                last_updated=datetime.now(),
                            )
                            db.add(asset)
                            
                        # Backfill missing Trade.price_at_transaction
                        missing_trades = db.query(Trade).join(TargetPerson).filter(
                            Trade.ticker == ticker,
                            Trade.price_at_transaction == None,
                            ((TargetPerson.is_tracked == True) | (TargetPerson.is_followed == True))
                        ).all()
                        
                        for trade in missing_trades:
                            if not trade.trade_date: continue
                            t_date = pd.Timestamp(trade.trade_date).normalize()
                            # Find exact or next available within 7 days
                            for days_offset in range(7):
                                check_date = t_date + pd.Timedelta(days=days_offset)
                                if check_date in s.index:
                                    trade.price_at_transaction = float(s.loc[check_date])
                                    break
                            
                        logger.info(f"Updated {ticker}: ${current_price:.2f}, YTD: {ytd_pct}%, Backfilled: {len(missing_trades)} trades")
                    except Exception as e:
                        logger.error(f"Failed processing {ticker} in batch: {e}")
                        
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "too many requests" in err_str:
                    logger.error("Yahoo Finance Rate Limit 429 Hit! Pausing for 1 hour.")
                    _runtime_overrides["rate_limit_until"] = datetime.now() + timedelta(hours=1)
                    notify_system_event(db, "⚠️ Yahoo Finance Rate Limit", "AInsider Tracker encountered a 429 Too Many Requests error from Yahoo Finance. Background price updates have been paused for 1 hour.")
                    db.commit()
                    return
                else:
                    logger.error(f"Failed fetching batch chunk: {e}")

        db.commit()
        logger.info("Price update complete")
        try:
            from app.routers.settings import _runtime_overrides
            _runtime_overrides["last_price_update"] = datetime.now()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Price update batch failed: {e}")
        db.rollback()
    finally:
        db.close()