"""
AInsider Tracker – Trades Router
Endpoints for querying and filtering trades.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Trade, TargetPerson, AssetPerformance
from app.schemas import TradeOut, TradeList

router = APIRouter(prefix="/api/trades", tags=["Trades"])


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
        from fastapi import HTTPException
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
