"""
AInsider Tracker – Trades Router
Endpoints for querying and filtering trades.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, case
from typing import Optional, List

from app.database import get_db
from app.models import Trade, TargetPerson, AssetPerformance
from app.schemas import (
    TradeOut, TradeList, AssetListOut, AssetSummaryOut, 
    AssetDetailOut, AssetInsiderSummary, LookupResultOut,
    LookupPersonOut, LookupAssetOut, ClusterSignalOut, ClusterListOut
)

router = APIRouter(prefix="/api/trades", tags=["Trades"])

TICKER_INFO = {
    "AAPL": {"name": "Apple Inc.", "isin": "US0378331005"},
    "MSFT": {"name": "Microsoft Corporation", "isin": "US5949181045"},
    "TSLA": {"name": "Tesla, Inc.", "isin": "US88160R1014"},
    "NVDA": {"name": "NVIDIA Corporation", "isin": "US67066G1040"},
    "SE": {"name": "Sea Limited", "isin": "US81141R1005"},
    "PLTR": {"name": "Palantir Technologies Inc.", "isin": "US69608A1088"},
    "AMD": {"name": "Advanced Micro Devices, Inc.", "isin": "US0079031078"},
    "BABA": {"name": "Alibaba Group Holding Limited", "isin": "US01609W1027"},
    "INTC": {"name": "Intel Corporation", "isin": "US4581401001"},
    "DIS": {"name": "The Walt Disney Company", "isin": "US2546871060"},
    "JPM": {"name": "JPMorgan Chase & Co.", "isin": "US46625H1005"},
    "BAC": {"name": "Bank of America Corporation", "isin": "US0605051046"},
    "TT": {"name": "Trane Technologies plc", "isin": "IE00B6S95B28"},
    "SAP": {"name": "SAP SE", "isin": "DE0007164600"},
    "BMW": {"name": "Bayerische Motoren Werke AG", "isin": "DE0005190003"},
    "AMZN": {"name": "Amazon.com, Inc.", "isin": "US0231351067"},
    "GOOGL": {"name": "Alphabet Inc.", "isin": "US02079K3059"},
    "GOOG": {"name": "Alphabet Inc.", "isin": "US02079K1079"},
    "META": {"name": "Meta Platforms, Inc.", "isin": "US30303M1027"},
    "NFLX": {"name": "Netflix, Inc.", "isin": "US64110L1061"},
    "PYPL": {"name": "PayPal Holdings, Inc.", "isin": "US70450Y1038"},
    "CRM": {"name": "Salesforce, Inc.", "isin": "US79466L3024"},
    "UBER": {"name": "Uber Technologies, Inc.", "isin": "US90353T1007"},
    "UNH": {"name": "UnitedHealth Group Incorporated", "isin": "US91324P1021"},
    "V": {"name": "Visa Inc.", "isin": "US92826C8394"},
    "MA": {"name": "Mastercard Incorporated", "isin": "US57636Q1040"},
    "WMT": {"name": "Walmart Inc.", "isin": "US9311421039"},
    "XOM": {"name": "Exxon Mobil Corporation", "isin": "US30231G1022"},
    "CVX": {"name": "Chevron Corporation", "isin": "US1667641005"},
    "RHEINMETALL": {"name": "Rheinmetall AG", "isin": "DE0007030009"},
    "SIEMENS": {"name": "Siemens AG", "isin": "DE0007236101"},
}


def resolve_ticker_and_isin(symbol_or_isin: str):
    clean = (symbol_or_isin or "").strip().upper()
    if not clean:
        return clean, "", f"{clean} Stock"
    
    # 1. Direct ticker match
    if clean in TICKER_INFO:
        return clean, TICKER_INFO[clean]["isin"], TICKER_INFO[clean]["name"]
    
    # 2. Check if clean matches any ISIN in dictionary
    for ticker_key, info in TICKER_INFO.items():
        if info["isin"].upper() == clean:
            return ticker_key, info["isin"], info["name"]
            
    # 3. Default fallback logic
    isin = clean if (clean.startswith("US") or clean.startswith("DE") or clean.startswith("IE") or len(clean) == 12) else f"US0{clean[:3]}901002"
    return clean, isin, f"{clean} Stock"


@router.get("/assets", response_model=AssetListOut)
def get_assets(
    search: Optional[str] = Query(None, description="Search by symbol, ISIN, or company name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get aggregated list of all traded assets/symbols with ISINs and insider counts."""
    # Subquery aggregating trades per ticker
    stats_query = (
        db.query(
            Trade.ticker,
            func.count(Trade.id).label("trade_count"),
            func.sum(case((Trade.type == "BUY", 1), else_=0)).label("buy_count"),
            func.sum(case((Trade.type == "SELL", 1), else_=0)).label("sell_count"),
            func.count(distinct(Trade.target_person_id)).label("distinct_insiders_count"),
            func.max(Trade.trade_date).label("last_trade_date"),
        )
        .group_by(Trade.ticker)
        .all()
    )

    # Fetch all asset performance records for lookup
    perf_records = {p.ticker: p for p in db.query(AssetPerformance).all()}

    asset_list = []
    search_term = (search or "").strip().upper()

    for row in stats_query:
        ticker = row.ticker
        resolved_ticker, isin, company_name = resolve_ticker_and_isin(ticker)
        perf = perf_records.get(ticker)

        # Search filter match check (ticker, isin, or company name)
        if search_term:
            matches = (
                search_term in ticker.upper() or
                search_term in isin.upper() or
                search_term in company_name.upper()
            )
            if not matches:
                continue

        asset_list.append(
            AssetSummaryOut(
                ticker=ticker,
                isin=isin,
                company_name=company_name,
                trade_count=row.trade_count or 0,
                buy_count=int(row.buy_count or 0),
                sell_count=int(row.sell_count or 0),
                distinct_insiders_count=row.distinct_insiders_count or 0,
                last_trade_date=row.last_trade_date,
                current_price=perf.current_price if perf else None,
                ytd_performance_pct=perf.ytd_performance_pct if perf else None,
            )
        )

    # Sort assets by trade count & last trade date descending
    asset_list.sort(key=lambda a: (a.trade_count, a.last_trade_date or ""), reverse=True)
    total = len(asset_list)
    paginated_assets = asset_list[offset: offset + limit]

    return AssetListOut(assets=paginated_assets, total=total)


@router.get("/symbols/{symbol_or_isin}", response_model=AssetDetailOut)
def get_symbol_detail(
    symbol_or_isin: str,
    db: Session = Depends(get_db)
):
    """Get detailed transaction overview and insider breakdown for a specific Symbol or ISIN."""
    clean_input = symbol_or_isin.strip().upper()
    resolved_ticker, isin, company_name = resolve_ticker_and_isin(clean_input)

    # Find matching trades in DB (by resolved_ticker or raw input)
    trades = (
        db.query(Trade)
        .join(TargetPerson)
        .filter(
            (func.upper(Trade.ticker) == resolved_ticker.upper()) | 
            (func.upper(Trade.ticker) == clean_input)
        )
        .order_by(Trade.trade_date.desc())
        .all()
    )

    if not trades and clean_input in TICKER_INFO:
        # Check if ISIN was passed matching TICKER_INFO
        alt_ticker = TICKER_INFO[clean_input]["isin"]
        trades = (
            db.query(Trade)
            .join(TargetPerson)
            .filter(func.upper(Trade.ticker) == alt_ticker.upper())
            .order_by(Trade.trade_date.desc())
            .all()
        )

    # Performance lookup
    actual_ticker = trades[0].ticker if trades else resolved_ticker
    perf = db.query(AssetPerformance).filter(AssetPerformance.ticker == actual_ticker).first()

    # Calculate insider breakdown
    insiders_dict = {}
    trade_out_list = []
    buy_count = 0
    sell_count = 0

    for t in trades:
        if t.type == "BUY":
            buy_count += 1
        else:
            sell_count += 1

        p_id = t.target_person_id
        if p_id not in insiders_dict:
            insiders_dict[p_id] = {
                "person_id": p_id,
                "person_name": t.person.name,
                "person_category": t.person.category,
                "photo_url": t.person.custom_photo_url or t.person.photo_url,
                "trade_count": 0,
                "buy_count": 0,
                "sell_count": 0,
            }
        insiders_dict[p_id]["trade_count"] += 1
        if t.type == "BUY":
            insiders_dict[p_id]["buy_count"] += 1
        else:
            insiders_dict[p_id]["sell_count"] += 1

        # Calculate return since purchase
        ret_pct = None
        if t.price_at_transaction and t.price_at_transaction > 0 and perf and perf.current_price:
            ret_pct = round(((perf.current_price - t.price_at_transaction) / t.price_at_transaction) * 100, 2)

        trade_out_list.append(
            TradeOut(
                id=t.id,
                target_person_id=t.target_person_id,
                person_name=t.person.name,
                person_category=t.person.category,
                person_photo_url=t.person.custom_photo_url or t.person.photo_url,
                ticker=t.ticker,
                type=t.type,
                amount_range=t.amount_range,
                trade_date=t.trade_date,
                filing_date=t.filing_date,
                source_url=t.source_url,
                price_at_transaction=t.price_at_transaction,
                return_since_purchase_pct=ret_pct,
                ai_score=t.ai_score,
                ai_summary=t.ai_summary,
                created_at=t.created_at
            )
        )

    insiders_summary = [AssetInsiderSummary(**v) for v in insiders_dict.values()]
    insiders_summary.sort(key=lambda i: i.trade_count, reverse=True)

    # Compute cluster signal if 2+ distinct buyers exist
    buyers = [v for v in insiders_dict.values() if v["buy_count"] > 0]
    cluster_sig = None
    if len(buyers) >= 2:
        buyer_names = [b["person_name"] for b in buyers]
        buy_trades = [t for t in trades if t.type == "BUY"]
        first_b = buy_trades[-1].trade_date if buy_trades else None
        latest_b = buy_trades[0].trade_date if buy_trades else None
        cluster_sig = ClusterSignalOut(
            ticker=actual_ticker,
            isin=isin,
            company_name=company_name,
            distinct_buyers_count=len(buyers),
            buyer_names=buyer_names,
            trade_count=sum(b["buy_count"] for b in buyers),
            first_buy_date=first_b,
            latest_buy_date=latest_b,
            current_price=perf.current_price if perf else None,
            ytd_performance_pct=perf.ytd_performance_pct if perf else None,
        )

    return AssetDetailOut(
        ticker=actual_ticker,
        isin=isin,
        company_name=company_name,
        current_price=perf.current_price if perf else None,
        ytd_performance_pct=perf.ytd_performance_pct if perf else None,
        trade_count=len(trades),
        buy_count=buy_count,
        sell_count=sell_count,
        distinct_insiders_count=len(insiders_dict),
        cluster_signal=cluster_sig,
        insiders=insiders_summary,
        trades=trade_out_list,
    )


@router.get("/clusters", response_model=ClusterListOut)
def get_clusters(
    days: int = Query(60, ge=7, le=180),
    min_buyers: int = Query(2, ge=2, le=10),
    db: Session = Depends(get_db)
):
    """Get co-buying cluster signals (assets where 2+ distinct insiders bought recently)."""
    from datetime import date, timedelta
    cutoff_date = date.today() - timedelta(days=days)
    INVALID_TICKERS = {"NONE", "NONE.", "N/A", "NA", "NULL", "UNKNOWN", ""}

    buy_trades = (
        db.query(Trade)
        .join(TargetPerson)
        .filter(
            Trade.type == "BUY", 
            Trade.trade_date >= cutoff_date,
            Trade.ticker.isnot(None),
            ~Trade.ticker.in_(INVALID_TICKERS)
        )
        .order_by(Trade.trade_date.desc())
        .all()
    )

    cluster_dict = {}
    for t in buy_trades:
        tick = t.ticker.strip().upper()
        if tick in INVALID_TICKERS:
            continue

        if tick not in cluster_dict:
            cluster_dict[tick] = {
                "ticker": tick,
                "buyer_ids": set(),
                "buyer_names": [],
                "trade_count": 0,
                "first_buy_date": t.trade_date,
                "latest_buy_date": t.trade_date,
            }
        
        info = cluster_dict[tick]
        info["trade_count"] += 1
        if t.target_person_id not in info["buyer_ids"]:
            info["buyer_ids"].add(t.target_person_id)
            info["buyer_names"].append(t.person.name)
        
        if t.trade_date < info["first_buy_date"]:
            info["first_buy_date"] = t.trade_date
        if t.trade_date > info["latest_buy_date"]:
            info["latest_buy_date"] = t.trade_date

    res_clusters = []
    perf_records = {p.ticker: p for p in db.query(AssetPerformance).all()}

    for tick, info in cluster_dict.items():
        distinct_count = len(info["buyer_ids"])
        if distinct_count >= min_buyers:
            resolved_ticker, isin, company_name = resolve_ticker_and_isin(tick)
            perf = perf_records.get(tick)

            res_clusters.append(
                ClusterSignalOut(
                    ticker=tick,
                    isin=isin,
                    company_name=company_name,
                    distinct_buyers_count=distinct_count,
                    buyer_names=info["buyer_names"],
                    trade_count=info["trade_count"],
                    first_buy_date=info["first_buy_date"],
                    latest_buy_date=info["latest_buy_date"],
                    current_price=perf.current_price if perf else None,
                    ytd_performance_pct=perf.ytd_performance_pct if perf else None,
                )
            )

    res_clusters.sort(key=lambda c: (c.distinct_buyers_count, c.trade_count), reverse=True)
    return ClusterListOut(clusters=res_clusters, total=len(res_clusters))


@router.get("/lookup", response_model=LookupResultOut)
def unified_lookup(
    q: str = Query(..., min_length=1, description="Search term for persons, symbols, ISINs, or companies"),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Unified search endpoint for persons and stock assets."""
    search_term = q.strip()
    if not search_term:
        return LookupResultOut(persons=[], assets=[])

    INVALID_TICKERS = {"NONE", "NONE.", "N/A", "NA", "NULL", "UNKNOWN", ""}

    # 1. Search TargetPersons
    person_query = (
        db.query(TargetPerson)
        .filter(
            (TargetPerson.name.ilike(f"%{search_term}%")) |
            (TargetPerson.display_name.ilike(f"%{search_term}%"))
        )
        .order_by(TargetPerson.is_tracked.desc(), TargetPerson.name)
        .limit(limit)
        .all()
    )

    matched_persons = []
    for p in person_query:
        cnt = db.query(func.count(Trade.id)).filter(Trade.target_person_id == p.id).scalar() or 0
        matched_persons.append(
            LookupPersonOut(
                id=p.id,
                name=p.name,
                display_name=p.display_name,
                category=p.category,
                photo_url=p.custom_photo_url or p.photo_url,
                is_tracked=p.is_tracked,
                trade_count=cnt
            )
        )

    # 2. Search Assets (symbols, ISINs, company names)
    stats_query = (
        db.query(
            Trade.ticker,
            func.count(Trade.id).label("trade_count"),
            func.count(distinct(Trade.target_person_id)).label("distinct_insiders_count")
        )
        .filter(
            Trade.ticker.isnot(None),
            ~Trade.ticker.in_(INVALID_TICKERS)
        )
        .group_by(Trade.ticker)
        .all()
    )

    matched_assets = []
    st_upper = search_term.upper()

    for row in stats_query:
        ticker = row.ticker
        if not ticker or ticker.upper() in INVALID_TICKERS:
            continue
        resolved_ticker, isin, company_name = resolve_ticker_and_isin(ticker)
        if (
            st_upper in ticker.upper() or
            st_upper in isin.upper() or
            st_upper in company_name.upper()
        ):
            matched_assets.append(
                LookupAssetOut(
                    ticker=ticker,
                    isin=isin,
                    company_name=company_name,
                    trade_count=row.trade_count or 0,
                    distinct_insiders_count=row.distinct_insiders_count or 0
                )
            )

    matched_assets.sort(key=lambda a: a.trade_count, reverse=True)

    return LookupResultOut(
        persons=matched_persons,
        assets=matched_assets[:limit]
    )


@router.get("", response_model=TradeList)
def get_trades(
    person_id: Optional[int] = Query(None, description="Filter by person ID"),
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    category: Optional[str] = Query(None, description="Filter by person category"),
    trade_type: Optional[str] = Query(None, description="Filter by BUY or SELL"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get trades with optional filters and pagination."""
    query = db.query(Trade).join(TargetPerson)

    if person_id:
        query = query.filter(Trade.target_person_id == person_id)
    if ticker:
        query = query.filter(Trade.ticker == ticker.upper())
    if category:
        query = query.filter(TargetPerson.category == category)
    if trade_type:
        query = query.filter(Trade.type == trade_type.upper())

    total = query.count()
    trades = query.order_by(Trade.trade_date.desc()).offset(offset).limit(limit).all()

    res_trades = []
    for t in trades:
        ret_pct = None
        if t.price_at_transaction and t.price_at_transaction > 0:
            perf = db.query(AssetPerformance).filter(AssetPerformance.ticker == t.ticker).first()
            if perf and perf.current_price:
                ret_pct = round(((perf.current_price - t.price_at_transaction) / t.price_at_transaction) * 100, 2)
        res_trades.append(
            TradeOut(
                id=t.id,
                target_person_id=t.target_person_id,
                person_name=t.person.name,
                person_category=t.person.category,
                person_photo_url=t.person.custom_photo_url or t.person.photo_url,
                ticker=t.ticker,
                type=t.type,
                amount_range=t.amount_range,
                trade_date=t.trade_date,
                filing_date=t.filing_date,
                source_url=t.source_url,
                price_at_transaction=t.price_at_transaction,
                return_since_purchase_pct=ret_pct,
                ai_score=t.ai_score,
                ai_summary=t.ai_summary,
                created_at=t.created_at
            )
        )

    return TradeList(
        trades=res_trades,
        total=total,
    )


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """Get a single trade by ID."""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    ret_pct = None
    if trade.price_at_transaction and trade.price_at_transaction > 0:
        perf = db.query(AssetPerformance).filter(AssetPerformance.ticker == trade.ticker).first()
        if perf and perf.current_price:
            ret_pct = round(((perf.current_price - trade.price_at_transaction) / trade.price_at_transaction) * 100, 2)

    return TradeOut(
        id=trade.id,
        target_person_id=trade.target_person_id,
        person_name=trade.person.name,
        person_category=trade.person.category,
        person_photo_url=trade.person.custom_photo_url or trade.person.photo_url,
        ticker=trade.ticker,
        type=trade.type,
        amount_range=trade.amount_range,
        trade_date=trade.trade_date,
        filing_date=trade.filing_date,
        source_url=trade.source_url,
        price_at_transaction=trade.price_at_transaction,
        return_since_purchase_pct=ret_pct,
        ai_score=trade.ai_score,
        ai_summary=trade.ai_summary,
        created_at=trade.created_at
    )

