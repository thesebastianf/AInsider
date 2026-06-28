"""
AInsider Tracker – Performance Router
Endpoints for asset performance data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import AssetPerformance
from app.schemas import AssetPerformanceOut

router = APIRouter(prefix="/api/performance", tags=["Performance"])


@router.get("", response_model=List[AssetPerformanceOut])
def get_all_performance(db: Session = Depends(get_db)):
    """Get performance data for all tracked assets."""
    assets = db.query(AssetPerformance).order_by(AssetPerformance.ticker).all()
    return [AssetPerformanceOut.model_validate(a) for a in assets]


@router.get("/{ticker}", response_model=AssetPerformanceOut)
def get_performance(ticker: str, db: Session = Depends(get_db)):
    """Get performance data for a specific ticker."""
    asset = db.query(AssetPerformance).filter(
        AssetPerformance.ticker == ticker.upper()
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"No performance data for {ticker}")
    return AssetPerformanceOut.model_validate(asset)
