"""
AInsider Tracker – Persons Router
Endpoints for querying target persons, following/unfollowing.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import TargetPerson, Trade
from app.schemas import PersonOut, PersonList, TradeOut, PersonBase

router = APIRouter(prefix="/api/persons", tags=["Persons"])


@router.post("", response_model=PersonOut, status_code=201)
def create_person(data: PersonBase, db: Session = Depends(get_db)):
    """Manually create a target person to be tracked."""
    existing = db.query(TargetPerson).filter(TargetPerson.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Person with this name already exists")
    
    person = TargetPerson(
        name=data.name,
        category=data.category,
        committee_affiliations=data.committee_affiliations or [],
        photo_url=data.photo_url,
        description=data.description,
        is_followed=True
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return _build_person_response(person, db)


def _build_person_response(person: TargetPerson, db: Session) -> PersonOut:
    """Build a PersonOut response including the latest trade and statistics."""
    from datetime import date, timedelta
    
    latest_trade = (
        db.query(Trade)
        .filter(Trade.target_person_id == person.id)
        .order_by(Trade.trade_date.desc())
        .first()
    )
    trade_count = (
        db.query(func.count(Trade.id))
        .filter(Trade.target_person_id == person.id)
        .scalar()
    ) or 0

    trade_count_30d = (
        db.query(func.count(Trade.id))
        .filter(
            Trade.target_person_id == person.id,
            Trade.trade_date >= date.today() - timedelta(days=30)
        )
        .scalar()
    ) or 0

    buy_count = (
        db.query(func.count(Trade.id))
        .filter(Trade.target_person_id == person.id, Trade.type == "BUY")
        .scalar()
    ) or 0

    sell_count = (
        db.query(func.count(Trade.id))
        .filter(Trade.target_person_id == person.id, Trade.type == "SELL")
        .scalar()
    ) or 0

    # Calculate average trade return pct based on actual price_at_transaction
    from app.models import AssetPerformance
    trades_for_perf = db.query(Trade).filter(
        Trade.target_person_id == person.id,
        Trade.price_at_transaction.isnot(None)
    ).all()
    
    avg_return_pct = None
    if trades_for_perf:
        returns = []
        for t in trades_for_perf:
            perf_entry = db.query(AssetPerformance).filter(AssetPerformance.ticker == t.ticker).first()
            if perf_entry and perf_entry.current_price and t.price_at_transaction > 0:
                ret = ((perf_entry.current_price - t.price_at_transaction) / t.price_at_transaction) * 100
                returns.append(ret)
        if returns:
            avg_return_pct = round(sum(returns) / len(returns), 2)

    from app.models import Subscription
    is_subscribed = (
        db.query(Subscription)
        .filter(
            Subscription.target_person_id == person.id,
            Subscription.user_id == "default"
        )
        .first() is not None
    )

    return PersonOut(
        id=person.id,
        name=person.name,
        category=person.category,
        committee_affiliations=person.committee_affiliations or [],
        photo_url=person.photo_url,
        description=person.description,
        is_tracked=person.is_tracked,
        is_followed=person.is_followed,
        is_subscribed=is_subscribed,
        latest_trade=TradeOut.model_validate(latest_trade) if latest_trade else None,
        trade_count=trade_count,
        trade_count_30d=trade_count_30d,
        buy_count=buy_count,
        sell_count=sell_count,
        avg_trade_return_pct=avg_return_pct,
    )


@router.get("", response_model=PersonList)
def get_persons(
    search: Optional[str] = Query(None, description="Search by name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    followed_only: bool = Query(False, description="Only show followed persons"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get target persons with optional search and category filter (defaulting to tracked only)."""
    query = db.query(TargetPerson).filter(TargetPerson.is_tracked == True)

    if search:
        query = query.filter(TargetPerson.name.ilike(f"%{search}%"))
    if category:
        query = query.filter(TargetPerson.category == category)
    if followed_only:
        query = query.filter(TargetPerson.is_followed == True)  # noqa: E712

    total = query.count()
    persons = query.order_by(TargetPerson.name).offset(offset).limit(limit).all()

    return PersonList(
        persons=[_build_person_response(p, db) for p in persons],
        total=total,
    )


@router.get("/available/list", response_model=PersonList)
def get_available_persons(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get target persons that are NOT currently tracked (available to be tracked)."""
    query = db.query(TargetPerson).filter(TargetPerson.is_tracked == False)
    if search:
        query = query.filter(TargetPerson.name.ilike(f"%{search}%"))
    if category:
        query = query.filter(TargetPerson.category == category)
        
    total = query.count()
    persons = query.order_by(TargetPerson.name).limit(100).all()
    
    return PersonList(
        persons=[_build_person_response(p, db) for p in persons],
        total=total
    )


@router.put("/{person_id}/track")
def toggle_tracking(person_id: int, is_tracked: bool = Query(True), db: Session = Depends(get_db)):
    """Toggle tracking status (is_tracked) for a target person."""
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
        
    person.is_tracked = is_tracked
    db.commit()
    db.refresh(person)
    return {"id": person.id, "is_tracked": person.is_tracked}


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db)):
    """Get a single person by ID."""
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return _build_person_response(person, db)


@router.put("/{person_id}/follow")
def toggle_follow(person_id: int, db: Session = Depends(get_db)):
    """Toggle the follow status of a person."""
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person.is_followed = not person.is_followed
    db.commit()
    db.refresh(person)

    return {"id": person.id, "is_followed": person.is_followed}


@router.put("/{person_id}/subscribe")
def toggle_subscription(person_id: int, db: Session = Depends(get_db)):
    """Toggle the notification subscription status of a person for user 'default'."""
    from app.models import Subscription
    
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing = db.query(Subscription).filter(
        Subscription.user_id == "default",
        Subscription.target_person_id == person.id
    ).first()

    if existing:
        db.delete(existing)
        is_sub = False
    else:
        db_sub = Subscription(user_id="default", target_person_id=person.id)
        db.add(db_sub)
        is_sub = True

    db.commit()
    return {"id": person.id, "is_subscribed": is_sub}
