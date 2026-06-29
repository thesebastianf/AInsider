"""add display_name and custom_photo_url to target_persons

Revision ID: 002_add_custom_fields
Revises: 001_initial
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "002_add_custom_fields"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("target_persons", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column("target_persons", sa.Column("custom_photo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("target_persons", "display_name")
    op.drop_column("target_persons", "custom_photo_url")
