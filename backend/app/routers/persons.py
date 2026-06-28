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
from app.schemas import PersonOut, PersonList, TradeOut

router = APIRouter(prefix="/api/persons", tags=["Persons"])


def _build_person_response(person: TargetPerson, db: Session) -> PersonOut:
    """Build a PersonOut response including the latest trade."""
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
    )

    return PersonOut(
        id=person.id,
        name=person.name,
        category=person.category,
        committee_affiliations=person.committee_affiliations or [],
        is_followed=person.is_followed,
        latest_trade=TradeOut.model_validate(latest_trade) if latest_trade else None,
        trade_count=trade_count or 0,
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
    """Get target persons with optional search and category filter."""
    query = db.query(TargetPerson)

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
