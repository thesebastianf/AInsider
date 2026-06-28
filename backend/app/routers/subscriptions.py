"""
AInsider Tracker – Subscriptions Router
Manage notification subscriptions for tracked persons.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Subscription, TargetPerson
from app.schemas import SubscriptionCreate, SubscriptionOut

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.get("", response_model=List[SubscriptionOut])
def get_subscriptions(
    user_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    """Get all subscriptions for a user."""
    subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    return [SubscriptionOut.model_validate(s) for s in subs]


@router.post("", response_model=SubscriptionOut, status_code=201)
def create_subscription(
    sub: SubscriptionCreate,
    user_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    """Create a new notification subscription."""
    person = db.query(TargetPerson).filter(TargetPerson.id == sub.target_person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.target_person_id == sub.target_person_id,
    ).first()
    if existing:
        return SubscriptionOut.model_validate(existing)

    db_sub = Subscription(user_id=user_id, target_person_id=sub.target_person_id)
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return SubscriptionOut.model_validate(db_sub)


@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Delete a subscription."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(sub)
    db.commit()
    return None
