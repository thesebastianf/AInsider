"""
AInsider Tracker – Application Configuration
Reads settings from environment variables / .env file.
LLM and Notification providers are stored in the database (UI-configurable).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://ainsider:changeme@localhost:5432/ainsider"

    # ─── Application ──────────────────────────────────────────
    SCHEDULER_INTERVAL_MINUTES: int = 30
    PRICE_UPDATE_INTERVAL_MINUTES: int = 15
    LOG_LEVEL: str = "INFO"
    DEBUG_MODE: bool = False

    # ─── Notifications ────────────────────────────────────────
    # Trades filed/traded longer ago than this are stored but not alerted
    # (prevents floods when a feed re-delivers or backfills old history).
    NOTIFY_MAX_AGE_DAYS: int = 60
    # More new trades than this for one person in one run → one digest message.
    NOTIFY_DIGEST_THRESHOLD: int = 3
    # Alert when a ticker newly enters the Top-N "Most traded" / "Multi-buyer" lists
    NOTIFY_HOT_STOCKS: bool = True
    HOT_STOCKS_TOP_N: int = 10
    HOT_STOCKS_STATE_FILE: str = "logs/hot_stocks_state.json"

    # ─── Optional Initial Seeding ─────────────────────────────
    SEED_LLM_PROVIDER: str | None = None
    SEED_LLM_URL: str | None = None
    SEED_LLM_MODEL: str | None = None
    SEED_LLM_API_KEY: str | None = None
    
    SEED_NOTIFY_PROVIDER: str | None = None
    SEED_NOTIFY_CONFIG: str | None = None

    SEED_DATASOURCE_PROVIDER: str | None = None
    SEED_DATASOURCE_CONFIG: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
