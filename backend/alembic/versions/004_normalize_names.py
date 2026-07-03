"""normalize existing names

Revision ID: 004_normalize_names
Revises: 003_increase_ticker_length
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "004_normalize_names"
down_revision = "003_increase_ticker_length"
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
                    
                    # Merge: re-point all trades and subscriptions
                    session.execute(
                        sa.update(trades)
                        .where(trades.c.target_person_id == p_id)
                        .values(target_person_id=existing_id)
                    )
                    session.execute(
                        sa.update(subscriptions)
                        .where(subscriptions.c.target_person_id == p_id)
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
