"""Add is_delisted to asset_performance

Revision ID: 002_add_is_delisted
Revises: 001_initial
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_is_delisted"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "asset_performance",
        sa.Column("is_delisted", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade() -> None:
    op.drop_column("asset_performance", "is_delisted")
