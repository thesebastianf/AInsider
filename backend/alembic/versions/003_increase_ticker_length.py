"""increase ticker length

Revision ID: 003_increase_ticker_length
Revises: 002_add_is_delisted
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_increase_ticker_length"
down_revision = "002_add_is_delisted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('trades', 'ticker', type_=sa.String(20))
    op.alter_column('asset_performance', 'ticker', type_=sa.String(20))


def downgrade() -> None:
    op.alter_column('trades', 'ticker', type_=sa.String(10))
    op.alter_column('asset_performance', 'ticker', type_=sa.String(10))
