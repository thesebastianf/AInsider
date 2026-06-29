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
    """Update prices for all tickers associated with tracked/followed persons in batch."""
    db = SessionLocal()
    try:
        from app.models import TargetPerson, Trade
        import yfinance as yf
        import pandas as pd
        from datetime import date
        
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

        # Fetch history from start of year to today for YTD calculation
        year_start = date(date.today().year, 1, 1)
        
        chunk_size = 50
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            if not chunk: continue
            
            try:
                data = yf.download(chunk, start=year_start.isoformat(), end=date.today().isoformat(), progress=False, auto_adjust=False)
                if data.empty or 'Close' not in data:
                    continue
                    
                close_data = data['Close']
                
                for ticker in chunk:
                    try:
                        if len(chunk) == 1:
                            s = close_data.dropna()
                        else:
                            if ticker not in close_data: continue
                            s = close_data[ticker].dropna()
                            
                        if s.empty: continue
                        
                        current_price = float(s.iloc[-1])
                        start_price = float(s.iloc[0])
                        
                        ytd_pct = None
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
                            
                        logger.info(f"Updated {ticker}: ${current_price:.2f}, YTD: {ytd_pct}%")
                    except Exception as e:
                        logger.error(f"Failed processing {ticker} in batch: {e}")
                        
            except Exception as e:
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


        for ticker in tickers:
            update_ticker_price(ticker, db)

        logger.info("Price update complete")
        try:
            from app.routers.settings import _runtime_overrides
            _runtime_overrides["last_price_update"] = datetime.now()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Price update batch failed: {e}")
    finally:
        db.close()
