"""
AInsider Tracker – Persons Router
Endpoints for querying target persons, following/unfollowing.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import os, uuid, shutil
from pathlib import Path

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

    year_start = date(date.today().year, 1, 1)
    thirty_days_ago = date.today() - timedelta(days=30)

    latest_trade = (
        db.query(Trade)
        .filter(Trade.target_person_id == person.id)
        .order_by(Trade.trade_date.desc())
        .first()
    )

    # Single aggregated query for all counts + date range
    agg = db.query(
        func.count(Trade.id).label("total"),
        func.count(Trade.id).filter(Trade.trade_date >= thirty_days_ago).label("last_30d"),
        func.count(Trade.id).filter(Trade.trade_date >= year_start).label("ytd_total"),
        func.count(Trade.id).filter(Trade.type == "BUY").label("buys"),
        func.count(Trade.id).filter(Trade.type == "SELL").label("sells"),
        func.count(Trade.id).filter(Trade.type == "BUY", Trade.trade_date >= year_start).label("ytd_buys"),
        func.count(Trade.id).filter(Trade.type == "SELL", Trade.trade_date >= year_start).label("ytd_sells"),
        func.min(Trade.trade_date).label("first_date"),
        func.max(Trade.trade_date).label("last_date"),
    ).filter(Trade.target_person_id == person.id).one()

    trade_count      = agg.total or 0
    trade_count_30d  = agg.last_30d or 0
    ytd_trade_count  = agg.ytd_total or 0
    buy_count        = agg.buys or 0
    sell_count       = agg.sells or 0
    ytd_buy_count    = agg.ytd_buys or 0
    ytd_sell_count   = agg.ytd_sells or 0
    first_trade_date = agg.first_date
    last_trade_date  = agg.last_date

    # Calculate average trade return pct based on actual price_at_transaction
    from app.models import AssetPerformance
    avg_return_pct = None
    try:
        trades_for_perf = db.query(Trade).filter(
            Trade.target_person_id == person.id,
            Trade.price_at_transaction.isnot(None)
        ).all()
        if trades_for_perf:
            returns = []
            for t in trades_for_perf:
                perf_entry = db.query(AssetPerformance).filter(AssetPerformance.ticker == t.ticker).first()
                if perf_entry and perf_entry.current_price and t.price_at_transaction and t.price_at_transaction > 0:
                    ret = ((perf_entry.current_price - t.price_at_transaction) / t.price_at_transaction) * 100
                    returns.append(ret)
            if returns:
                avg_return_pct = round(sum(returns) / len(returns), 2)
    except Exception:
        pass

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
        display_name=person.display_name,
        category=person.category,
        committee_affiliations=person.committee_affiliations or [],
        photo_url=person.photo_url,
        custom_photo_url=person.custom_photo_url,
        description=person.description,
        is_tracked=person.is_tracked,
        is_followed=person.is_followed,
        is_subscribed=is_subscribed,
        latest_trade=TradeOut.model_validate(latest_trade) if latest_trade else None,
        trade_count=trade_count,
        trade_count_30d=trade_count_30d,
        ytd_trade_count=ytd_trade_count,
        buy_count=buy_count,
        sell_count=sell_count,
        ytd_buy_count=ytd_buy_count,
        ytd_sell_count=ytd_sell_count,
        first_trade_date=first_trade_date,
        last_trade_date=last_trade_date,
        avg_trade_return_pct=avg_return_pct,
    )


@router.get("", response_model=PersonList)
def get_persons(
    search: Optional[str] = Query(None, description="Search by name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    followed_only: bool = Query(False, description="Only show followed persons"),
    sort_by: Optional[str] = Query('name', description="Sort by: name, trade_count, performance, recent_trade"),
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
    persons = query.all()

    # Build response objects first so we can sort by dynamically calculated fields
    response_persons = [_build_person_response(p, db) for p in persons]

    # Sort
    if sort_by == 'trade_count':
        response_persons.sort(key=lambda x: (not x.is_followed, -x.trade_count))
    elif sort_by == 'performance':
        response_persons.sort(key=lambda x: (not x.is_followed, -(x.avg_trade_return_pct if x.avg_trade_return_pct is not None else -99999.0)))
    elif sort_by == 'recent_trade':
        response_persons.sort(key=lambda x: (not x.is_followed, -(x.latest_trade.trade_date.toordinal()) if x.latest_trade and x.latest_trade.trade_date else 0))
    else:
        # Default to name sorting (case insensitive)
        response_persons.sort(key=lambda x: (not x.is_followed, x.name.lower()))

    # Apply pagination in Python
    paginated = response_persons[offset:offset + limit]

    return PersonList(
        persons=paginated,
        total=total,
    )


@router.get("/available/list", response_model=PersonList)
def get_available_persons(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort_by: Optional[str] = Query('name', description="Sort by: name, trade_count, recent_trade"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get target persons that are NOT currently tracked (available to be tracked)."""
    query = db.query(TargetPerson).filter(TargetPerson.is_tracked == False)
    if search:
        query = query.filter(TargetPerson.name.ilike(f"%{search}%"))
    if category:
        query = query.filter(TargetPerson.category == category)
        
    total = query.count()
    
    if sort_by == 'trade_count':
        query = query.outerjoin(Trade).group_by(TargetPerson.id).order_by(func.count(Trade.id).desc())
    elif sort_by == 'recent_trade':
        query = query.outerjoin(Trade).group_by(TargetPerson.id).order_by(func.max(Trade.trade_date).desc())
    else:
        query = query.order_by(TargetPerson.name)

    persons = query.offset(offset).limit(limit).all()
    
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


# ─────────────────────────────────────────────────────────────────
# Custom Name (alias) & Photo Endpoints
# ─────────────────────────────────────────────────────────────────

class PersonPatch(BaseModel if False else object):
    pass

from pydantic import BaseModel as _BaseModel

class PersonDisplayUpdate(_BaseModel):
    display_name: Optional[str] = None  # None = revert to original name


@router.put("/{person_id}/display-name")
def update_display_name(
    person_id: int,
    data: PersonDisplayUpdate,
    db: Session = Depends(get_db)
):
    """Set or clear a custom display name for a person.
    The original `name` field is never modified (it's the dedup key).
    Pass display_name=null or empty string to revert to original.
    """
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Empty string or explicit None = revert
    person.display_name = data.display_name.strip() if data.display_name and data.display_name.strip() else None
    db.commit()
    db.refresh(person)
    return {
        "id": person.id,
        "name": person.name,
        "display_name": person.display_name,
        "effective_name": person.display_name or person.name,
    }


# Photo upload storage: /app/uploads (Docker volume) or local dev fallback
_UPLOAD_DIR = Path("/app/uploads") if Path("/app").exists() else Path(__file__).parent.parent.parent / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Static serving prefix
_UPLOADS_URL_PREFIX = "/uploads"


@router.post("/{person_id}/upload-photo")
async def upload_photo(
    person_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a custom profile photo for a person.
    Stores file under /app/uploads/ and sets custom_photo_url.
    """
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Validate content type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP or GIF images are allowed")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"person_{person_id}_{uuid.uuid4().hex[:8]}.{ext}"
    dest = _UPLOAD_DIR / filename

    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    # Store URL relative to static server root
    url = f"{_UPLOADS_URL_PREFIX}/{filename}"
    person.custom_photo_url = url
    db.commit()
    db.refresh(person)
    return {"id": person.id, "custom_photo_url": url}


@router.delete("/{person_id}/upload-photo")
def delete_custom_photo(
    person_id: int,
    db: Session = Depends(get_db)
):
    """Remove the custom uploaded photo for a person (reverts to auto-fetched photo)."""
    person = db.query(TargetPerson).filter(TargetPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person.custom_photo_url:
        filename = person.custom_photo_url.split("/")[-1]
        dest = _UPLOAD_DIR / filename
        if dest.exists():
            dest.unlink(missing_ok=True)
    person.custom_photo_url = None
    db.commit()
    return {"id": person.id, "custom_photo_url": None}
