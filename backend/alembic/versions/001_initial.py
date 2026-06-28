"""Initial migration – create all tables

Revision ID: 001_initial
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── target_persons ───────────────────────────────────────
    op.create_table(
        "target_persons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("committee_affiliations", sa.JSON(), server_default="[]"),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_followed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── trades ───────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_person_id", sa.Integer(),
                  sa.ForeignKey("target_persons.id"), nullable=False, index=True),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("type", sa.String(4), nullable=False),
        sa.Column("amount_range", sa.String(50), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date()),
        sa.Column("source_url", sa.String(500)),
        sa.Column("ai_score", sa.Integer()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "target_person_id", "ticker", "trade_date", "amount_range",
            name="uq_trade_dedup"
        ),
    )

    # ─── asset_performance ────────────────────────────────────
    op.create_table(
        "asset_performance",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("current_price", sa.Float()),
        sa.Column("ytd_performance_pct", sa.Float()),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── subscriptions ────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(50), nullable=False, server_default="default"),
        sa.Column("target_person_id", sa.Integer(),
                  sa.ForeignKey("target_persons.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── llm_config ───────────────────────────────────────────
    op.create_table(
        "llm_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("api_url", sa.String(500), nullable=False),
        sa.Column("api_key", sa.String(500)),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── notification_config ──────────────────────────────────
    op.create_table(
        "notification_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_test", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── datasource_config ────────────────────────────────────
    op.create_table(
        "datasource_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_fetch", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("datasource_config")
    op.drop_table("notification_config")
    op.drop_table("llm_config")
    op.drop_table("subscriptions")
    op.drop_table("asset_performance")
    op.drop_table("trades")
    op.drop_table("target_persons")
