"""
AInsider Tracker – Trade Data Fetcher Strategy
Fetches trade data from multiple configured real sources.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from dataclasses import dataclass
import httpx
import re
from sqlalchemy.orm import Session
from abc import ABC, abstractmethod

from app.database import SessionLocal
from app.models import DataSourceConfig
from app.config import settings

logger = logging.getLogger("ainsider.fetcher")

def fetch_wikipedia_photo(name: str) -> Optional[str]:
    """Attempt to fetch a 300px thumbnail from Wikipedia for a person's name."""
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&titles={name.replace(' ', '%20')}&prop=pageimages&format=json&pithumbsize=300"
        # Must include User-Agent with email per Wikimedia policy
        headers = {'User-Agent': 'AInsiderTrackerBot/1.0 (admin@ainsidertracker.com)'}
        resp = httpx.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for _, page in pages.items():
                if "thumbnail" in page:
                    return page["thumbnail"].get("source")
    except Exception as e:
        logger.debug(f"Could not fetch Wikipedia photo for {name}: {e}")
    return None


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
    """Fetches ALL historical House trades from the HouseStockWatcher S3 bulk dataset.
    
    This endpoint returns the complete archive of House trade disclosures since ~2012,
    not just recent filings. No API key required.
    """
    
    BULK_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
    FALLBACK_URL = "https://congress.kadoa.com/data/trades.json"

    def fetch_trades(self, limit: int = 5000) -> List[RawTrade]:
        trades = []
        try:
            headers = {
                "User-Agent": "AInsiderTrackerAdmin admin@ainsidertracker.com"
            }
            # Try the S3 bulk endpoint first (full history since 2012)
            resp = httpx.get(self.BULK_URL, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"HouseStockWatcher: Loaded {len(data)} total records from bulk dataset")

        except Exception as bulk_err:
            logger.warning(f"HouseStockWatcher: Bulk S3 fetch failed ({bulk_err}), falling back to Kadoa live feed")
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = httpx.get(self.FALLBACK_URL, headers=headers, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                # Fallback: filter for house chamber
                data = [item for item in data if item.get("chamber") == "house"]
            except Exception as fallback_err:
                logger.error(f"HouseStockWatcher: All endpoints failed: {fallback_err}")
                try:
                    from app.routers.system import add_log
                    add_log("ERROR", f"HouseStockWatcher fetch failed: {str(fallback_err)[:150]}")
                except Exception:
                    pass
                return []

        for item in data:
            try:
                ticker = item.get("ticker")
                if not ticker or ticker == "--" or len(ticker) > 10:
                    continue
                ticker = ticker.strip().upper()

                t_date_str = item.get("transaction_date", "")
                if not t_date_str:
                    continue

                # Bulk dataset uses YYYY-MM-DD
                try:
                    td = date.fromisoformat(t_date_str)
                except ValueError:
                    continue

                trade_type_raw = (item.get("type") or item.get("transaction_type", "")).upper()
                if "PURCHASE" in trade_type_raw or "BUY" in trade_type_raw:
                    trade_type = "BUY"
                elif "SALE" in trade_type_raw or "SELL" in trade_type_raw:
                    trade_type = "SELL"
                else:
                    continue

                representative = (
                    item.get("representative") or
                    item.get("filer_name") or
                    "Unknown"
                )

                trade = RawTrade(
                    person_name=representative,
                    person_category="Congress",
                    committees=[],
                    ticker=ticker,
                    trade_type=trade_type,
                    amount_range=item.get("amount") or item.get("amount_range_label") or "$1,001-$15,000",
                    trade_date=td,
                    filing_date=date.fromisoformat(item["disclosure_date"]) if item.get("disclosure_date") else None,
                    source_url=item.get("pdf_url") or item.get("doc_url"),
                )
                trades.append(trade)
            except Exception as e:
                logger.debug(f"HouseStockWatcher: Skipping malformed trade entry: {e}")
                continue

        logger.info(f"HouseStockWatcher: Parsed {len(trades)} valid trades")
        return trades



class ExecutiveBranchProvider(BaseDataSourceProvider):
    """Fetches Executive Branch (OGE Form 278-T) trades from Kadoa dataset."""
    
    URL = "https://congress.kadoa.com/data/trades.json"

    def fetch_trades(self, limit: int = 5000) -> List[RawTrade]:
        trades = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            
            # Filter for executive branch or OGE
            data = [item for item in data if item.get("branch") == "executive" or "executive" in str(item.get("agency", "")).lower()]
            logger.info(f"ExecutiveBranch: Loaded {len(data)} total records from Kadoa dataset")
            
            for item in data:
                try:
                    ticker = item.get("ticker", "").strip()
                    if not ticker or ticker == "--" or len(ticker) > 10:
                        continue
                        
                    t_date_str = item.get("transaction_date")
                    if not t_date_str:
                        continue
                        
                    try:
                        td = date.fromisoformat(t_date_str)
                    except ValueError:
                        continue
                        
                    trade_type_raw = (item.get("type") or item.get("transaction_type", "")).upper()
                    if "PURCHASE" in trade_type_raw or "BUY" in trade_type_raw:
                        trade_type = "BUY"
                    elif "SALE" in trade_type_raw or "SELL" in trade_type_raw:
                        trade_type = "SELL"
                    else:
                        continue
                        
                    representative = (
                        item.get("filer_name") or
                        "Unknown"
                    )
                    
                    agency = item.get("agency") or "Executive Branch"
                    
                    trade = RawTrade(
                        person_name=representative,
                        person_category="Executive Branch",
                        committees=[agency],
                        ticker=ticker,
                        trade_type=trade_type,
                        amount_range=item.get("amount") or item.get("amount_range_label") or "$1,001-$15,000",
                        trade_date=td,
                        filing_date=date.fromisoformat(item["filing_date"]) if item.get("filing_date") else None,
                        source_url=item.get("doc_url") or "",
                    )
                    trades.append(trade)
                except Exception as e:
                    logger.debug(f"ExecutiveBranch: Skipping malformed trade entry: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"ExecutiveBranch: Fetch failed: {e}")
            try:
                from app.routers.system import add_log
                add_log("ERROR", f"Executive Branch Data Source failed: {e}")
            except Exception:
                pass
                
        logger.info(f"ExecutiveBranch: Parsed {len(trades)} valid trades")
        return trades

class SenateStockWatcherProvider(BaseDataSourceProvider):
    """Fetches ALL historical Senate trades from the senate-stock-watcher-data GitHub archive.
    
    Loads the full aggregate dataset (all senators, all years) — not just the most recent filings.
    No API key required.
    """
    
    URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"

    def fetch_trades(self, limit: int = 10000) -> List[RawTrade]:
        trades = []
        try:
            headers = {
                "User-Agent": "AInsiderTrackerAdmin admin@ainsidertracker.com"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"SenateStockWatcher: Loaded {len(data)} total records from bulk dataset")

            for item in data:
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
                        try:
                            td = date.fromisoformat(trade_date_str)
                        except ValueError:
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
                    logger.debug(f"SenateStockWatcher: Skipping malformed trade entry: {e}")
                    continue

            logger.info(f"SenateStockWatcher: Parsed {len(trades)} valid trades")

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
    """Fetches quarterly portfolio holdings from SEC EDGAR 13F filings.
    
    Parses institutional investment manager holdings for specified fund CIKs.
    Data is completely free via the official SEC EDGAR REST API.
    
    config_json should contain:
        cik_list: comma-separated CIKs to track, e.g. "0002045724,0001350694"
    
    Notable CIKs:
        0002045724 - Situational Awareness LP (Leopold Aschenbrenner)
        0001350694 - Berkshire Hathaway Inc
        0001067983 - Berkshire Hathaway (Warren Buffett, main entity)
        0001336528 - BlackRock Inc
    
    Note: 13F filings report portfolio *holdings* at end-of-quarter, not individual
    buy/sell transactions. We represent each holding as a synthetic BUY trade on the
    report date so they appear in the trade feed.
    """
    
    EDGAR_BASE = "https://data.sec.gov"
    HEADERS = {"User-Agent": "AInsiderTrackerAdmin admin@ainsidertracker.com"}

    def _get_recent_13f_filing(self, cik_padded: str) -> Optional[dict]:
        """Get the most recent 13F-HR filing metadata for a CIK."""
        url = f"{self.EDGAR_BASE}/submissions/{cik_padded}.json"
        try:
            resp = httpx.get(url, headers=self.HEADERS, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])
            
            # Find most recent 13F-HR
            for i, form in enumerate(forms):
                if form in ("13F-HR", "13F-HR/A"):
                    return {
                        "accession": accessions[i].replace("-", ""),
                        "accession_dashed": accessions[i],
                        "filing_date": filing_dates[i],
                        "cik_padded": cik_padded,
                        "entity_name": data.get("name", "Unknown Fund"),
                    }
        except Exception as e:
            logger.warning(f"SEC13F: Could not fetch filing list for CIK {cik_padded}: {e}")
        return None

    def _parse_13f_holdings(self, filing: dict) -> List[RawTrade]:
        """Parse the XML holdings table from a 13F-HR filing."""
        import xml.etree.ElementTree as ET
        
        trades = []
        cik_num = filing["cik_padded"].lstrip("CIK").lstrip("0")
        accession = filing["accession"]
        entity_name = filing["entity_name"]
        
        try:
            filing_date = date.fromisoformat(filing["filing_date"])
        except Exception:
            filing_date = date.today()
        
        # Step 1: Get the filing index to find the infotable XML
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accession}/"
            f"{filing['accession_dashed']}-index.htm"
        )
        try:
            import time
            time.sleep(0.5)  # Respect SEC rate limit (10 req/sec)
            index_resp = httpx.get(index_url, headers=self.HEADERS, timeout=15.0)
            
            # Find the infotable XML link
            xml_links = re.findall(r'href="(/Archives/edgar/data/[^"]+\.xml)"', index_resp.text, re.IGNORECASE)
            valid_xmls = [l for l in xml_links if 'xsl' not in l.lower()]
            infotable_links = [l for l in valid_xmls if 'primary_doc.xml' not in l.lower()]
            
            if infotable_links:
                xml_match_url = infotable_links[0]
            elif valid_xmls:
                xml_match_url = valid_xmls[0]
            else:
                logger.warning(f"SEC13F: Could not find infotable XML for {entity_name}")
                return []
            
            xml_url = "https://www.sec.gov" + xml_match_url
            time.sleep(0.5)
            xml_resp = httpx.get(xml_url, headers=self.HEADERS, timeout=15.0)
            xml_resp.raise_for_status()
            
            # Parse the infotable XML — namespace varies
            xml_content = xml_resp.content
            root = ET.fromstring(xml_content)
            
            # SEC 13F XML namespace (varies by year)
            ns_candidates = [
                "{http://www.sec.gov/edgar/document/thirteenf/informationtable}",
                "{http://www.sec.gov/edgar/document/thirteenf/informationTable}",
                "",
            ]
            
            info_table = None
            for ns_prefix in ns_candidates:
                entries = root.findall(f"{ns_prefix}infoTable")
                if entries:
                    info_table = entries
                    break
                # Also check nested
                entries = root.findall(f".//{ns_prefix}infoTable")
                if entries:
                    info_table = entries
                    break
            
            if not info_table:
                logger.warning(f"SEC13F: No infoTable entries found for {entity_name}")
                return []
            
            for entry in info_table[:200]:  # Max 200 positions per filing
                try:
                    def get_text(elem, tag):
                        for ns in ns_candidates:
                            node = elem.find(f"{ns}{tag}")
                            if node is not None and node.text:
                                return node.text.strip()
                        return ""
                    
                    ticker = get_text(entry, "ticker") or get_text(entry, "issuerName", )
                    if not ticker:
                        # Use issuerName as ticker placeholder
                        issuer = get_text(entry, "nameOfIssuer")
                        if not issuer:
                            continue
                        # Extract ticker-like abbreviation
                        ticker = issuer.split()[0].upper()[:6]
                    
                    ticker = ticker.upper().strip()
                    if len(ticker) > 10 or not ticker:
                        continue
                    
                    shares_raw = get_text(entry, "sshPrnamt")
                    if not shares_raw:
                        # Sometimes it's nested inside shrsOrPrnAmt
                        for ns in ns_candidates:
                            container = entry.find(f"{ns}shrsOrPrnAmt")
                            if container is not None:
                                node = container.find(f"{ns}sshPrnamt")
                                if node is not None and node.text:
                                    shares_raw = node.text.strip()
                                    break
                    
                    value_raw = get_text(entry, "value")
                    
                    shares = int(float(shares_raw)) if shares_raw else 0
                    value_usd = int(float(value_raw)) if value_raw else 0
                    
                    if value_usd >= 1_000_000:
                        amount_range = f"${value_usd / 1_000_000:.1f}M ({shares:,} sh)"
                    elif value_usd >= 1_000:
                        amount_range = f"${value_usd / 1_000:.0f}K ({shares:,} sh)"
                    else:
                        amount_range = f"{shares:,} shares"
                    
                    trade = RawTrade(
                        person_name=entity_name,
                        person_category="Fund Manager",
                        committees=[],
                        ticker=ticker,
                        trade_type="BUY",  # 13F holdings are reported as positions held
                        amount_range=amount_range[:50],
                        trade_date=filing_date,
                        filing_date=filing_date,
                        source_url=xml_url,
                    )
                    trades.append(trade)
                except Exception as e:
                    logger.debug(f"SEC13F: Skipping holding entry: {e}")
                    continue
            
            logger.info(f"SEC13F: Parsed {len(trades)} holdings for {entity_name} ({filing['filing_date']})")
        
        except Exception as e:
            logger.error(f"SEC13F: Failed to parse holdings for {entity_name}: {e}")
        
        return trades

    def fetch_trades(self, limit: int = 500) -> List[RawTrade]:
        """Fetch 13F holdings for all configured CIKs."""
        cfg = self.config.config_json or {}
        cik_list_raw = cfg.get("cik_list", "")
        
        if not cik_list_raw:
            logger.warning("SEC13F: No CIKs configured. Using defaults (Aschenbrenner, Buffett).")
            cik_list_raw = "2045724,1067983"
            
        cik_list = [c.strip().zfill(10) for c in cik_list_raw.split(",") if c.strip()]
        all_trades = []
        
        for cik in cik_list:
            cik_key = f"CIK{cik}"
            filing = self._get_recent_13f_filing(cik_key)
            if filing:
                holdings = self._parse_13f_holdings(filing)
                all_trades.extend(holdings)
            else:
                logger.warning(f"SEC13F: No 13F filing found for CIK {cik}")
        
        return all_trades


class SEC13DProvider(BaseDataSourceProvider):
    """Fetches SEC 13D/13G (Activist Investor) filings for configured CIKs."""
    
    def _get_recent_submissions(self, cik_key: str) -> dict:
        url = f"https://data.sec.gov/submissions/{cik_key}.json"
        headers = {"User-Agent": "AInsiderTrackerAdmin admin@ainsidertracker.com"}
        try:
            resp = httpx.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"SEC13D: Error fetching submissions for {cik_key}: {e}")
        return {}

    def fetch_trades(self, limit: int = 50) -> List[RawTrade]:
        cfg = self.config.config_json or {}
        cik_list_raw = cfg.get("cik_list", "")
        if not cik_list_raw:
            logger.warning("SEC13D: No CIKs configured. Using defaults (Icahn, Pershing Square).")
            cik_list_raw = "0000921669,0001336528"
            
        cik_list = [c.strip().zfill(10) for c in cik_list_raw.split(",") if c.strip()]
        trades = []
        
        from datetime import date
        for cik in cik_list:
            cik_key = f"CIK{cik}"
            data = self._get_recent_submissions(cik_key)
            if not data:
                continue
                
            entity_name = data.get("name", f"Activist CIK {cik}")
            filings = data.get("filings", {}).get("recent", {})
            if not filings:
                continue
                
            # Parse the recent filings arrays
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            acc_nums = filings.get("accessionNumber", [])
            docs = filings.get("primaryDocument", [])
            
            for i in range(len(forms)):
                if forms[i] in ("SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"):
                    # We found an activist filing!
                    acc_num = str(acc_nums[i]).replace("-", "")
                    doc = docs[i]
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_num}/{doc}"
                    
                    try:
                        td = date.fromisoformat(dates[i])
                    except:
                        td = date.today()
                        
                    # Since SEC 13D submissions json doesn't list the target ticker,
                    # we use a generic placeholder or attempt to extract it if we had a full parser.
                    # For now, we will record the ticker as the activist's own entity name or "ACTIVIST".
                    # A true implementation would parse the SGML header of the filing for the subject company CUSIP.
                    ticker = "ACTV"
                    
                    trade = RawTrade(
                        person_name=entity_name,
                        person_category="Activist Investor",
                        committees=[],
                        ticker=ticker,
                        trade_type="BUY", # 13D is always an acquisition of >5%
                        amount_range=">5% Ownership",
                        trade_date=td,
                        filing_date=td,
                        source_url=url,
                    )
                    trades.append(trade)
                    if len(trades) >= limit:
                        return trades
        return trades


class FinnhubForm4Provider(BaseDataSourceProvider):
    """Fetches real insider trades from SEC EDGAR Form 4 filings via Finnhub."""
    
    URL = "https://finnhub.io/api/v1/stock/insider-transactions"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        cfg = self.config.config_json or {}
        api_key = cfg.get("api_key", "").strip()
        if not api_key:
            logger.warning("Finnhub API Key is missing for SEC Form 4")
            return []
            
        ticker_list_raw = cfg.get("ticker_list", "AAPL,TSLA,MSFT")
        symbols = [s.strip().upper() for s in ticker_list_raw.split(",") if s.strip()]
        
        trades = []
        from datetime import date
        
        for symbol in symbols:
            try:
                resp = httpx.get(
                    f"{self.URL}?symbol={symbol}&token={api_key}",
                    timeout=10.0
                )
                if resp.status_code == 429:
                    logger.warning("Finnhub API rate limit exceeded")
                    break
                resp.raise_for_status()
                data = resp.json().get("data", [])
                
                for item in data[:limit]:
                    try:
                        code = item.get("transactionCode", "")
                        if code == "P":
                            trade_type = "BUY"
                        elif code == "S":
                            trade_type = "SELL"
                        else:
                            continue
                            
                        shares = item.get("share", 0)
                        if shares == 0:
                            continue
                        price = item.get("transactionPrice", 0)
                        val = shares * price
                        
                        if val > 0:
                            if val > 1_000_000:
                                amount_range = f"${val/1_000_000:.1f}M"
                            else:
                                amount_range = f"${val:,.0f}"
                        else:
                            amount_range = f"{shares:,} shares"
                            
                        td = date.fromisoformat(item.get("transactionDate", date.today().isoformat()))
                        
                        trade = RawTrade(
                            person_name=item.get("name", "Unknown Insider"),
                            person_category="Corporate Insider",
                            committees=[],
                            ticker=symbol,
                            trade_type=trade_type,
                            amount_range=amount_range,
                            trade_date=td,
                            filing_date=date.fromisoformat(item.get("filingDate", td.isoformat())),
                            source_url=f"https://finnhub.io/",
                        )
                        trades.append(trade)
                    except Exception as e:
                        logger.debug(f"SECForm4 (Finnhub): Skipping malformed trade: {e}")
                
                import time
                time.sleep(1.01)  # Guard against Finnhub rate limits
            except Exception as e:

                logger.error(f"SECForm4 (Finnhub): Error fetching {symbol}: {e}")
                
        return trades



class SECForm4Provider(BaseDataSourceProvider):
    """Fetches real insider trades from SEC EDGAR Form 4 filings."""
    
    URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom&count=100"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        trades = []
        headers = {
            "User-Agent": "AInsiderTrackerAdmin admin@ainsidertracker.com"
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
                    if not (title.startswith("4 -") or title.startswith("4/A -")):
                        continue
                        
                    index_url = link_elem.attrib.get("href", "")
                    if not index_url:
                        continue
                    
                    # 1. Fetch HTML index page to find the XML URL
                    index_resp = httpx.get(index_url, headers=headers, timeout=10.0)
                    if index_resp.status_code != 200:
                        continue
                        
                    # Find xml href (e.g. href="/Archives/edgar/data/1318605/000191234524012345/form4.xml")
                    xml_links = re.findall(r'href="(/Archives/edgar/data/[^"]+\.xml)"', index_resp.text)
                    valid_xmls = [l for l in xml_links if 'xsl' not in l.lower()]
                    if not valid_xmls:
                        continue
                        
                    xml_url = "https://www.sec.gov" + valid_xmls[0]
                    
                    # 2. Fetch the actual Form 4 XML
                    xml_resp = httpx.get(xml_url, headers=headers, timeout=10.0)
                    if xml_resp.status_code != 200:
                        continue
                        
                    xml_root = ET.fromstring(xml_resp.content)
                    from datetime import date
                    
                    # Target company details
                    issuer = xml_root.find("issuer")
                    if issuer is None: continue
                    ticker = getattr(issuer.find("issuerTradingSymbol"), "text", None)
                    if not ticker: continue
                    
                    # Reporting person
                    owner = xml_root.find("reportingOwner")
                    if owner is None: continue
                    owner_id = owner.find("reportingOwnerId")
                    person_name = getattr(owner_id.find("rptOwnerName"), "text", "Unknown") if owner_id is not None else "Unknown"
                    
                    # Non-derivative transactions
                    non_deriv = xml_root.find("nonDerivativeTable")
                    if non_deriv is None: continue
                    
                    for tx in non_deriv.findall("nonDerivativeTransaction"):
                        tx_date = getattr(tx.find("transactionDate/value"), "text", None)
                        tx_code = getattr(tx.find("transactionCoding/transactionCode"), "text", None)
                        
                        shares = float(getattr(tx.find("transactionAmounts/transactionShares/value"), "text", 0))
                        pps = float(getattr(tx.find("transactionAmounts/transactionPricePerShare/value"), "text", 0))
                        
                        if tx_code == "P":
                            t_type = "BUY"
                        elif tx_code == "S":
                            t_type = "SELL"
                        else:
                            continue
                            
                        amount = shares * pps
                        
                        trade = RawTrade(
                            person_name=person_name,
                            person_category="Corporate Insider",
                            committees=[],
                            ticker=ticker.upper(),
                            trade_type=t_type,
                            amount_range=f"${amount:,.0f}",
                            trade_date=date.fromisoformat(tx_date[:10]) if tx_date else date.today(),
                            filing_date=date.today(),
                            source_url=index_url
                        )
                        trades.append(trade)
                except Exception as e:
                    logger.debug(f"SECForm4: Skipping individual Form4 parse: {e}")
                    
        except Exception as e:
            logger.error(f"SECForm4: Master feed parsing failed: {e}")
            
        return trades

class DirectorsDealingsProvider(BaseDataSourceProvider):
    """Fetches and parses real European Directors' Dealings news from Wallstreet Online RSS feed."""
    
    URL = "https://www.wallstreet-online.de/rss/nachrichten-directors-dealings.xml"

    def fetch_trades(self, limit: int = 20) -> List[RawTrade]:
        import xml.etree.ElementTree as ET
        import re
        
        trades = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=30.0)
            resp.raise_for_status()
            
            root = ET.fromstring(resp.content)
            channel = root.find("channel")
            if channel is None:
                return []
                
            items = channel.findall("item")
            recent = items[:100]  # Read up to 100 recent entries to populate the archive
            
            for item in recent:
                try:
                    title = item.find("title").text or ""
                    # E.g. "EQS-DD: DATRON AG: ...", "DGAP-DD: Rheinmetall AG: ...", "DD: Company: ..."
                    # Match any string starting with DD tags or ending with -DD or -News before the colon
                    prefix_match = re.match(r"^([A-Za-z0-9\-]+)(?:-DD|-News|DD)?\s*:", title)
                    if not prefix_match:
                        continue
                        
                    # Verify it's actually a Directors' Dealings (DD) or related corporate news notification
                    prefix = prefix_match.group(1).upper()
                    if not any(x in prefix for x in ["EQS", "DGAP", "DD"]):
                        continue
                    
                    parts = title.split(":")
                    if len(parts) < 3:
                        continue
                        
                    company_name = parts[1].strip()
                    rest = ":".join(parts[2:]).strip()
                    
                    if "," in rest:
                        # Extract the name before the first comma to avoid long sentences
                        manager_name = rest.split(",")[0].strip()
                    else:
                        manager_name = rest.strip()
                        
                    # Clean up known transaction words if they ended up in the name
                    for word in [" Kauf", " Verkauf", " Erwerb", " Veräußerung", " Buy", " Sell", 
                                 " kauf", " verkauf", " erwerb"]:
                        if manager_name.endswith(word):
                            manager_name = manager_name[:-len(word)].strip()
                            
                    rest_upper = rest.upper()
                    if "VERKAUF" in rest_upper or "SELL" in rest_upper or "VERÄUSSERUNG" in rest_upper:
                        trade_type = "SELL"
                    else:
                        trade_type = "BUY"
                        
                    # Extract ticker from company name (first word uppercase)
                    ticker = company_name.split()[0].upper()
                    for suffix in ["AG", "SE", "KGAA", "PLC", "INC", "CORP", "GMBH"]:
                        if ticker.endswith(suffix):
                            ticker = ticker[:-len(suffix)]
                    ticker = "".join(c for c in ticker if c.isalnum())
                    if not ticker:
                        ticker = "GERMANY"
                        
                    # Parse date
                    date_element = item.find("{http://purl.org/dc/elements/1.1/}date")
                    if date_element is not None and date_element.text:
                        t_date = datetime.fromisoformat(date_element.text.strip()).date()
                    else:
                        t_date = date.today()
                        
                    # Fetch article content to extract exact volume
                    link = item.find("link").text or ""
                    amount_range = "> €50,000"
                    try:
                        article_resp = httpx.get(link, headers=headers, timeout=3.0)
                        if article_resp.status_code == 200:
                            amounts_raw = re.findall(r"([\d\.,]+)\s*(?:EUR|€)", article_resp.text)
                            floats = []
                            for val in amounts_raw:
                                cleaned = val.replace(".", "").replace(",", ".")
                                try:
                                    floats.append(float(cleaned))
                                except ValueError:
                                    pass
                            if floats:
                                max_val = max(floats)
                                if max_val >= 1000000:
                                    amount_range = f"€{max_val / 1000000:.1f}M"
                                elif max_val >= 1000:
                                    amount_range = f"€{max_val / 1000:.0f}K"
                                else:
                                    amount_range = f"€{max_val:.0f}"
                    except Exception:
                        pass
                        
                    trade = RawTrade(
                        person_name=manager_name,
                        person_category="Corporate Insider",
                        committees=[company_name],
                        ticker=ticker,
                        trade_type=trade_type,
                        amount_range=amount_range,
                        trade_date=t_date,
                        filing_date=t_date,
                        source_url=link,
                    )
                    trades.append(trade)
                    logger.info(f"Directors Dealings parsed: {manager_name} ({company_name}) {trade_type} {ticker}")
                except Exception as e:
                    logger.warning(f"DirectorsDealingsProvider: Skipping entry: {e}")
                    continue
        except Exception as e:
            logger.error(f"DirectorsDealingsProvider: Failed to parse feed: {e}")
            try:
                from app.routers.system import add_log
                add_log("ERROR", f"DirectorsDealingsProvider fetch failed: {str(e)[:150]}")
            except Exception:
                pass
                
        return trades


class SocialInverseCramerProvider(BaseDataSourceProvider):
    """Parses Quiver Quantitative's Jim Cramer CNBC tracker webpage directly.
    Transforms Cramers recommendations to inverse trade signals:
      - Buy / bullish call -> Synthetic SELL trade
      - Sell / bearish call -> Synthetic BUY trade
    Does not require any API Key, scrapes the public web page directly.
    """
    
    URL = "https://www.quiverquant.com/cnbctracker/Jim%20Cramer"

    def fetch_trades(self, limit: int = 150) -> List[RawTrade]:
        from datetime import datetime
        import re
        trades = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = httpx.get(self.URL, headers=headers, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(f"SocialInverseCramerProvider: Failed to fetch page, status {resp.status_code}")
                return []
                
            # Parse table rows from the HTML
            rows = re.findall(r"<tr.*?>(.*?)</tr>", resp.text, re.DOTALL)
            count = 0
            
            for r in rows:
                if count >= limit:
                    break
                    
                # Clean HTML tags to get pure text content of the row
                clean_row = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", r)).strip()
                if not clean_row or "Name *" in clean_row:
                    continue
                    
                # Check for structure: "Jim Cramer [Date] [Ticker] [Direction] [Notes]"
                if not clean_row.startswith("Jim Cramer"):
                    continue
                    
                # Parse with regex: "Jim Cramer {Date} {Ticker} {Direction} {Notes}"
                # Example: "Jim Cramer June 18, 2026 INTC Buy None -->"
                match = re.search(r"Jim\s+Cramer\s+([A-Za-z]+\s+\d+,\s+\d{4})\s+([A-Z]{1,5})\s+([A-Za-z\s\-\'\!]+)\s+([A-Za-z0-9]+)?", clean_row)
                if not match:
                    continue
                    
                date_str = match.group(1).strip()
                ticker = match.group(2).strip()
                direction = match.group(3).strip().lower()
                
                # Filter out interview segments or holds
                if "interview" in direction or "hold" in direction or "neutral" in direction:
                    continue
                    
                # Parse date
                try:
                    t_date = datetime.strptime(date_str, "%B %d, %Y").date()
                except Exception:
                    t_date = date.today()
                    
                # Inverse Logic: Cramer BUY/Bullish -> SELL, Cramer SELL/Bearish -> BUY
                is_buy = any(x in direction for x in ["buy", "bullish", "positive", "long", "start a position"])
                is_sell = any(x in direction for x in ["sell", "bearish", "negative", "avoid", "not recommending"])
                
                if is_buy and not is_sell:
                    trade_type = "SELL"
                elif is_sell and not is_buy:
                    trade_type = "BUY"
                else:
                    # Ignore if call direction is unclear
                    continue
                    
                trades.append(RawTrade(
                    person_name="Inverse Cramer",
                    person_category="Social",
                    committees=["Inverse Cramer Tracker"],
                    ticker=ticker,
                    trade_type=trade_type,
                    amount_range="$10k-$50k",
                    trade_date=t_date,
                    filing_date=t_date,
                    source_url=self.URL
                ))
                count += 1
                logger.info(f"Inverse Cramer parsed: {trade_type} {ticker} (Inverse of Cramer {direction.upper()} call on {date_str})")
        except Exception as e:
            logger.error(f"SocialInverseCramerProvider: Failed to scrape page: {e}")
        return trades


PROVIDER_CLASSES = {
    "house": HouseStockWatcherProvider,
    "senate": SenateStockWatcherProvider,
    "executive": ExecutiveBranchProvider,
    "quiver": QuiverQuantProvider,
    "sec13f": SEC13FProvider,
    "sec13d": SEC13DProvider,
    "sec_form4": SECForm4Provider,
    "finnhub": FinnhubForm4Provider,
    "directors_dealings": DirectorsDealingsProvider,
    "social_inverse_cramer": SocialInverseCramerProvider,
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
            
            cfg = dict(source.config_json or {})
            try:
                trades = provider.fetch_trades(limit=2000)
                all_trades.extend(trades)
                source.last_fetch = datetime.now()
                cfg["last_status"] = "success"
                cfg["last_count"] = len(trades)
                cfg["last_error"] = None
            except Exception as e:
                logger.error(f"Error fetching from data source {source.name}: {e}")
                cfg["last_status"] = "error"
                cfg["last_count"] = 0
                cfg["last_error"] = str(e)[:150]
                try:
                    from app.routers.system import add_log
                    add_log("ERROR", f"Failed fetching data source '{source.name}': {str(e)[:150]}")
                except Exception:
                    pass
            
            from sqlalchemy.orm.attributes import flag_modified
            source.config_json = cfg
            flag_modified(source, "config_json")
            
        db.commit()
    finally:
        db.close()

    return all_trades
