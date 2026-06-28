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

    return TradeList(
        trades=[TradeOut.model_validate(t) for t in trades],
        total=total,
    )


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """Get a single trade by ID."""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeOut.model_validate(trade)
