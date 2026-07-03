"""merge remaining names duplicate safe

Revision ID: 005_merge_remaining_names
Revises: 004_normalize_names
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "005_merge_remaining_names"
down_revision = "004_normalize_names"
branch_labels = None
depends_on = None

def normalize_person_name(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        corporate_suffixes = {"LP", "LLC", "INC", "CORP", "AG", "SE", "GMBH", "LTD", "PARTNERS", "ASSOCIATES"}
        if any(p.upper().replace(".", "") in corporate_suffixes for p in parts):
            return name
        
        if len(parts) == 2:
            last, first = parts
            return f"{first} {last}"
        elif len(parts) == 3:
            last, first, suffix = parts
            if suffix.lower() in ["jr.", "jr", "sr.", "sr", "ii", "iii", "iv"]:
                return f"{first} {last}, {suffix}"
            return f"{first} {last} {suffix}"
    return name

def upgrade() -> None:
    # Use Session to perform database-level updates
    bind = op.get_bind()
    session = Session(bind=bind)
    
    try:
        meta = sa.MetaData()
        target_persons = sa.Table('target_persons', meta, autoload_with=bind)
        trades = sa.Table('trades', meta, autoload_with=bind)
        subscriptions = sa.Table('subscriptions', meta, autoload_with=bind)
        
        # Fetch all target persons
        persons = session.execute(sa.select(target_persons)).fetchall()
        
        # Map to find duplicates after normalization
        # Structure: normalized_name -> TargetPerson.id
        name_to_id = {}
        
        for person in persons:
            p_id = person.id
            orig_name = person.name
            norm_name = normalize_person_name(orig_name)
            
            if norm_name != orig_name:
                existing_id = name_to_id.get(norm_name)
                if not existing_id:
                    # Let's check if there is another record with norm_name already in the table
                    other = session.execute(
                        sa.select(target_persons.c.id).where(target_persons.c.name == norm_name)
                    ).scalar()
                    if other:
                        existing_id = other
                
                if existing_id:
                    # Merge: check if target record has custom photo, if not copy it
                    existing_photo = session.execute(
                        sa.select(target_persons.c.custom_photo_url).where(target_persons.c.id == existing_id)
                    ).scalar()
                    if not existing_photo and person.custom_photo_url:
                        session.execute(
                            sa.update(target_persons)
                            .where(target_persons.c.id == existing_id)
                            .values(custom_photo_url=person.custom_photo_url)
                        )
                    
                    # Merge: carry over tracked/followed flags
                    orig_tp = session.execute(
                        sa.select(target_persons.c.is_tracked, target_persons.c.is_followed)
                        .where(target_persons.c.id == p_id)
                    ).first()
                    exist_tp = session.execute(
                        sa.select(target_persons.c.is_tracked, target_persons.c.is_followed)
                        .where(target_persons.c.id == existing_id)
                    ).first()
                    if orig_tp and exist_tp:
                        session.execute(
                            sa.update(target_persons)
                            .where(target_persons.c.id == existing_id)
                            .values(
                                is_tracked=orig_tp.is_tracked or exist_tp.is_tracked,
                                is_followed=orig_tp.is_followed or exist_tp.is_followed
                            )
                        )

                    # Merge: re-point trades, deleting duplicates
                    orig_trades = session.execute(
                        sa.select(trades.c.id, trades.c.ticker, trades.c.trade_date, trades.c.amount_range)
                        .where(trades.c.target_person_id == p_id)
                    ).fetchall()
                    
                    for t_row in orig_trades:
                        dup_exists = session.execute(
                            sa.select(trades.c.id).where(
                                trades.c.target_person_id == existing_id,
                                trades.c.ticker == t_row.ticker,
                                trades.c.trade_date == t_row.trade_date,
                                trades.c.amount_range == t_row.amount_range
                            )
                        ).scalar() is not None
                        
                        if dup_exists:
                            session.execute(
                                sa.delete(trades).where(trades.c.id == t_row.id)
                            )
                        else:
                            session.execute(
                                sa.update(trades)
                                .where(trades.c.id == t_row.id)
                                .values(target_person_id=existing_id)
                            )

                    # Merge: re-point subscriptions, deleting duplicates
                    orig_subs = session.execute(
                        sa.select(subscriptions.c.id, subscriptions.c.user_id)
                        .where(subscriptions.c.target_person_id == p_id)
                    ).fetchall()
                    
                    for s_row in orig_subs:
                        dup_exists = session.execute(
                            sa.select(subscriptions.c.id).where(
                                subscriptions.c.target_person_id == existing_id,
                                subscriptions.c.user_id == s_row.user_id
                            )
                        ).scalar() is not None
                        
                        if dup_exists:
                            session.execute(
                                sa.delete(subscriptions).where(subscriptions.c.id == s_row.id)
                            )
                        else:
                            session.execute(
                                sa.update(subscriptions)
                                .where(subscriptions.c.id == s_row.id)
                                .values(target_person_id=existing_id)
                            )

                    # Delete the duplicate person record
                    session.execute(
                        sa.delete(target_persons).where(target_persons.c.id == p_id)
                    )
                else:
                    # Just update the name
                    session.execute(
                        sa.update(target_persons)
                        .where(target_persons.c.id == p_id)
                        .values(name=norm_name)
                    )
                    name_to_id[norm_name] = p_id
            else:
                name_to_id[norm_name] = p_id
                
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def downgrade() -> None:
    pass
