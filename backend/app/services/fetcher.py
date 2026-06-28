"""
AInsider Tracker – Trade Data Fetcher Strategy
Fetches trade data from multiple configured real sources.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from dataclasses import dataclass
import httpx
from sqlalchemy.orm import Session
from abc import ABC, abstractmethod

from app.database import SessionLocal
from app.models import DataSourceConfig
from app.config import settings

logger = logging.getLogger("ainsider.fetcher")


@dataclass
class RawTrade:
    """Raw trade data before normalization."""
    person_name: str
    person_category: str
    committees: list
    ticker: str
    trade_type: str  # "BUY" or "SELL"
    amount_range: str
    trade_date: date
    filing_date: Optional[date] = None
    source_url: Optional[str] = None


class BaseDataSourceProvider(ABC):
    """Abstract base class for all data source providers."""
    
    def __init__(self, config: DataSourceConfig):
        self.config = config

    @abstractmethod
    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        """Fetch trades from the source."""
        pass


class HouseStockWatcherProvider(BaseDataSourceProvider):
    """Fetches real trades from House Stock Watcher API."""
    
    URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        trades = []
        try:
            resp = httpx.get(self.URL, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()

            recent = sorted(data, key=lambda x: x.get("transaction_date", ""), reverse=True)[:limit]

            for item in recent:
                try:
                    ticker = item.get("ticker", "").strip()
                    if not ticker or ticker == "--" or len(ticker) > 10:
                        continue

                    trade_date_str = item.get("transaction_date", "")
                    if not trade_date_str:
                        continue

                    parts = trade_date_str.split("-")
                    if len(parts) == 3:
                        td = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    else:
                        continue

                    trade_type_raw = item.get("type", "").upper()
                    if "PURCHASE" in trade_type_raw or "BUY" in trade_type_raw:
                        trade_type = "BUY"
                    elif "SALE" in trade_type_raw or "SELL" in trade_type_raw:
                        trade_type = "SELL"
                    else:
                        continue

                    trade = RawTrade(
                        person_name=item.get("representative", "Unknown"),
                        person_category="Congress",
                        committees=[],
                        ticker=ticker.upper(),
                        trade_type=trade_type,
                        amount_range=item.get("amount", "$1,001-$15,000"),
                        trade_date=td,
                        filing_date=None,
                        source_url=item.get("ptr_link"),
                    )
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"HouseStockWatcher: Skipping malformed trade entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"HouseStockWatcher: Failed to fetch data: {e}")
            try:
                from app.routers.system import add_log
                add_log("ERROR", f"HouseStockWatcher fetch failed: {str(e)[:150]}")
            except Exception:
                pass

        return trades


class SenateStockWatcherProvider(BaseDataSourceProvider):
    """Fetches real trades from Senate Stock Watcher API."""
    
    URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        trades = []
        try:
            resp = httpx.get(self.URL, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()

            recent = sorted(data, key=lambda x: x.get("transaction_date", ""), reverse=True)[:limit]

            for item in recent:
                try:
                    ticker = item.get("ticker", "").strip()
                    if not ticker or ticker == "--" or len(ticker) > 10:
                        continue

                    trade_date_str = item.get("transaction_date", "")
                    if not trade_date_str:
                        continue

                    parts = trade_date_str.split("/")
                    if len(parts) == 3:
                        td = date(int(parts[2]), int(parts[0]), int(parts[1]))
                    else:
                        continue

                    trade_type_raw = item.get("type", "").upper()
                    if "PURCHASE" in trade_type_raw or "BUY" in trade_type_raw:
                        trade_type = "BUY"
                    elif "SALE" in trade_type_raw or "SELL" in trade_type_raw:
                        trade_type = "SELL"
                    else:
                        continue

                    trade = RawTrade(
                        person_name=item.get("senator", "Unknown"),
                        person_category="Senate",
                        committees=[],
                        ticker=ticker.upper(),
                        trade_type=trade_type,
                        amount_range=item.get("amount", "$1,001-$15,000"),
                        trade_date=td,
                        filing_date=None,
                        source_url=item.get("ptr_link"),
                    )
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"SenateStockWatcher: Skipping malformed trade entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"SenateStockWatcher: Failed to fetch data: {e}")
            try:
                from app.routers.system import add_log
                add_log("ERROR", f"SenateStockWatcher fetch failed: {str(e)[:150]}")
            except Exception:
                pass

        return trades


class QuiverQuantProvider(BaseDataSourceProvider):
    """Fetches real trades via Quiver Quantitative API (Requires API Key)."""
    
    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        logger.warning("QuiverQuantProvider is not fully implemented yet.")
        try:
            from app.routers.system import add_log
            add_log("WARNING", "QuiverQuantProvider: Real-time API feed is not fully implemented yet.")
        except Exception:
            pass
        return []


class SEC13FProvider(BaseDataSourceProvider):
    """Fetches real trades from SEC EDGAR (13F Filings for Fund Managers)."""
    
    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        logger.warning("SEC13FProvider is not fully implemented yet.")
        try:
            from app.routers.system import add_log
            add_log("WARNING", "SEC13FProvider: SEC EDGAR 13F parsing is not fully implemented yet.")
        except Exception:
            pass
        return []


PROVIDER_CLASSES = {
    "house": HouseStockWatcherProvider,
    "senate": SenateStockWatcherProvider,
    "quiver": QuiverQuantProvider,
    "sec13f": SEC13FProvider,
}


def fetch_trades() -> List[RawTrade]:
    """Iterate over all enabled data sources in DB and fetch trades."""
    db: Session = SessionLocal()
    all_trades: List[RawTrade] = []
    
    try:
        active_sources = db.query(DataSourceConfig).filter(DataSourceConfig.is_enabled == True).all()
        
        if not active_sources:
            logger.warning("No active Data Source providers configured.")
            try:
                from app.routers.system import add_log
                add_log("WARNING", "No active Data Source providers enabled. Go to Settings -> Data Sources to activate them.")
            except Exception:
                pass
            return []

        for source in active_sources:
            provider_cls = PROVIDER_CLASSES.get(source.provider_type)
            if not provider_cls:
                logger.error(f"Unknown data source provider type: {source.provider_type}")
                try:
                    from app.routers.system import add_log
                    add_log("ERROR", f"Unknown data source provider type: {source.provider_type}")
                except Exception:
                    pass
                continue
                
            logger.info(f"Fetching from data source: {source.name} ({source.provider_type})")
            provider = provider_cls(source)
            trades = provider.fetch_trades(limit=2000)
            all_trades.extend(trades)
            
            # Update last fetch time
            source.last_fetch = datetime.now()
            
        db.commit()
    finally:
        db.close()

    return all_trades
