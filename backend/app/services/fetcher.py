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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=30.0)
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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=30.0)
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


class SECForm4Provider(BaseDataSourceProvider):
    """Fetches real insider trades from SEC EDGAR Form 4 filings."""
    
    URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        trades = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            resp = httpx.get(self.URL, headers=headers, timeout=30.0)
            resp.raise_for_status()
            
            import xml.etree.ElementTree as ET
            import re
            
            root = ET.fromstring(resp.content)
            # Atom namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)[:limit]
            
            for entry in entries:
                try:
                    title_elem = entry.find("atom:title", ns)
                    link_elem = entry.find("atom:link", ns)
                    if title_elem is None or link_elem is None:
                        continue
                        
                    title = title_elem.text or ""
                    index_url = link_elem.attrib.get("href", "")
                    if not index_url:
                        continue
                        
                    # Parse owner name and issuer company from title:
                    # e.g., "4 - Musk Elon (0001315535) (Subject) / TESLA, INC. (0001318605) (Issuer)"
                    match = re.search(r"4\s*-\s*([^(]+)\s*\(.*Subject\)\s*/\s*([^(]+)", title)
                    if not match:
                        continue
                        
                    owner_name = match.group(1).strip()
                    company_name = match.group(2).strip()
                    
                    # 1. Fetch HTML index page to find the XML URL
                    index_resp = httpx.get(index_url, headers=headers, timeout=10.0)
                    if index_resp.status_code != 200:
                        continue
                        
                    # Find xml href (e.g. href="/Archives/edgar/data/1318605/000191234524012345/form4.xml")
                    xml_match = re.search(r'href="(/Archives/edgar/data/[^"]+\.xml)"', index_resp.text)
                    if not xml_match:
                        continue
                        
                    xml_url = "https://www.sec.gov" + xml_match.group(1)
                    
                    # 2. Fetch the XML document
                    xml_resp = httpx.get(xml_url, headers=headers, timeout=10.0)
                    if xml_resp.status_code != 200:
                        continue
                        
                    xml_root = ET.fromstring(xml_resp.content)
                    
                    # 3. Parse Ticker Symbol
                    ticker_elem = xml_root.find(".//issuerTradingSymbol")
                    if ticker_elem is None or not ticker_elem.text:
                        continue
                    ticker = ticker_elem.text.strip().upper()
                    
                    # 4. Parse Corporate Title
                    title_elem = xml_root.find(".//officerTitle")
                    corporate_title = title_elem.text.strip() if (title_elem is not None and title_elem.text) else "Insider"
                    
                    # 5. Parse first transaction (non-derivative)
                    trans = xml_root.find(".//nonDerivativeTransaction")
                    if trans is None:
                        continue
                        
                    t_date_elem = trans.find(".//transactionDate/value")
                    t_code_elem = trans.find(".//transactionCoding/transactionCode")
                    t_shares_elem = trans.find(".//transactionAmounts/transactionShares/value")
                    t_price_elem = trans.find(".//transactionAmounts/transactionPricePerShare/value")
                    t_code_ad_elem = trans.find(".//transactionAmounts/transactionAcquiredDisposedCode/value")
                    
                    if t_date_elem is None or not t_date_elem.text:
                        continue
                        
                    # Date formatting (YYYY-MM-DD)
                    parts = t_date_elem.text.split("-")
                    if len(parts) == 3:
                        td = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    else:
                        continue
                        
                    # Determine BUY / SELL
                    code = t_code_elem.text if (t_code_elem is not None and t_code_elem.text) else ""
                    code_ad = t_code_ad_elem.text if (t_code_ad_elem is not None and t_code_ad_elem.text) else ""
                    
                    if code == "P" or code_ad == "A":
                        trade_type = "BUY"
                    elif code == "S" or code_ad == "D":
                        trade_type = "SELL"
                    else:
                        continue
                        
                    shares = float(t_shares_elem.text) if (t_shares_elem is not None and t_shares_elem.text) else 0.0
                    price = float(t_price_elem.text) if (t_price_elem is not None and t_price_elem.text) else 0.0
                    
                    value = shares * price
                    if value == 0:
                        amount_range = f"{int(shares):,} shares"
                    else:
                        amount_range = f"${value:,.2f} ({int(shares):,} sh @ ${price:,.2f})"
                        
                    trade = RawTrade(
                        person_name=owner_name,
                        person_category="Corporate Insider",
                        committees=[],
                        ticker=ticker,
                        trade_type=trade_type,
                        amount_range=amount_range[:50],
                        trade_date=td,
                        filing_date=date.today(),
                        source_url=xml_url,
                    )
                    trades.append(trade)
                    logger.info(f"Form 4 parsed: {owner_name} ({corporate_title} @ {company_name}) {trade_type} {ticker}")
                except Exception as e:
                    logger.warning(f"SECForm4Provider: Skipping entry: {e}")
                    continue
        except Exception as e:
            logger.error(f"SECForm4Provider: Failed to parse feed: {e}")
            try:
                from app.routers.system import add_log
                add_log("ERROR", f"SECForm4Provider fetch failed: {str(e)[:150]}")
            except Exception:
                pass
                
        return trades


PROVIDER_CLASSES = {
    "house": HouseStockWatcherProvider,
    "senate": SenateStockWatcherProvider,
    "quiver": QuiverQuantProvider,
    "sec13f": SEC13FProvider,
    "sec_form4": SECForm4Provider,
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
            try:
                trades = provider.fetch_trades(limit=2000)
                all_trades.extend(trades)
                # Update last fetch time
                source.last_fetch = datetime.now()
            except Exception as e:
                logger.error(f"Error fetching from data source {source.name}: {e}")
                try:
                    from app.routers.system import add_log
                    add_log("ERROR", f"Failed fetching data source '{source.name}': {str(e)[:150]}")
                except Exception:
                    pass
            
        db.commit()
    finally:
        db.close()

    return all_trades
