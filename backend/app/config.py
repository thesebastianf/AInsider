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


settings = Settings()
