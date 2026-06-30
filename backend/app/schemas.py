"""
AInsider Tracker – Pydantic Schemas
Request/Response models for the FastAPI endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


# ═══════════════════════════════════════════════════════════════
# Trade Schemas
# ═══════════════════════════════════════════════════════════════

class TradeOut(BaseModel):
    id: int
    target_person_id: int
    person_name: Optional[str] = None
    person_category: Optional[str] = None
    ticker: str
    type: str
    amount_range: str
    trade_date: date
    filing_date: Optional[date] = None
    source_url: Optional[str] = None
    price_at_transaction: Optional[float] = None
    return_since_purchase_pct: Optional[float] = None
    ai_score: Optional[int] = None
    ai_summary: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TradeList(BaseModel):
    trades: List[TradeOut]
    total: int


# ═══════════════════════════════════════════════════════════════
# Person Schemas
# ═══════════════════════════════════════════════════════════════

class PersonBase(BaseModel):
    name: str
    display_name: Optional[str] = None
    category: str
    committee_affiliations: Optional[List[str]] = []
    photo_url: Optional[str] = None
    custom_photo_url: Optional[str] = None
    description: Optional[str] = None
    is_tracked: Optional[bool] = False
    is_active: Optional[bool] = True


class PersonOut(PersonBase):
    id: int
    is_followed: bool = False
    is_subscribed: bool = False
    latest_trade: Optional[TradeOut] = None
    trade_count: int = 0
    trade_count_30d: int = 0
    ytd_trade_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    ytd_buy_count: int = 0
    ytd_sell_count: int = 0
    first_trade_date: Optional[date] = None
    last_trade_date: Optional[date] = None
    avg_trade_return_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None

    class Config:
        from_attributes = True


class PersonList(BaseModel):
    persons: List[PersonOut]
    total: int


# ═══════════════════════════════════════════════════════════════
# Asset Performance Schemas
# ═══════════════════════════════════════════════════════════════

class AssetPerformanceOut(BaseModel):
    ticker: str
    current_price: Optional[float] = None
    ytd_performance_pct: Optional[float] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# Subscription Schemas
# ═══════════════════════════════════════════════════════════════

class SubscriptionCreate(BaseModel):
    target_person_id: int


class SubscriptionOut(BaseModel):
    id: int
    user_id: str
    target_person_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# LLM Provider Schemas
# ═══════════════════════════════════════════════════════════════

class LLMConfigCreate(BaseModel):
    provider_type: str = Field(description="ollama, openai, anthropic, custom")
    name: str
    api_url: str
    api_key: Optional[str] = None
    model_name: str


class LLMConfigOut(BaseModel):
    id: int
    provider_type: str
    name: str
    api_url: str
    has_api_key: bool = False
    model_name: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class LLMTestResult(BaseModel):
    success: bool
    message: str
    response: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Notification Provider Schemas
# ═══════════════════════════════════════════════════════════════

NOTIFICATION_PROVIDER_FIELDS = {
    "telegram": {"bot_token": "Telegram Bot Token", "chat_id": "Chat ID"},
    "gotify": {"url": "Gotify Server URL", "app_token": "App Token"},
    "pushover": {"user_key": "User Key", "api_token": "API Token"},
    "discord": {"webhook_url": "Webhook URL"},
    "slack": {"webhook_url": "Webhook URL"},
    "ntfy": {"url": "Server URL", "topic": "Topic", "token": "Access Token (optional)"},
}


class NotificationConfigCreate(BaseModel):
    provider_type: str = Field(description="telegram, gotify, pushover, discord, slack, ntfy")
    name: str
    config_json: Dict[str, Any]


class NotificationConfigOut(BaseModel):
    id: int
    provider_type: str
    name: str
    config_json: Dict[str, Any]
    is_enabled: bool
    last_test: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationConfigUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None


class NotificationTestResult(BaseModel):
    success: bool
    message: str


# ═══════════════════════════════════════════════════════════════
# Settings Schemas
# ═══════════════════════════════════════════════════════════════

class AppSettingsOut(BaseModel):
    scheduler_interval_minutes: int
    price_update_interval_minutes: int
    last_pipeline_run: Optional[datetime] = None
    is_pipeline_running: bool = False
    notification_providers: List[NotificationConfigOut] = []
    data_source_providers: List['DataSourceConfigOut'] = []


class AppSettingsUpdate(BaseModel):
    scheduler_interval_minutes: Optional[int] = None
    price_update_interval_minutes: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# System / Developer Schemas
# ═══════════════════════════════════════════════════════════════

class SystemStats(BaseModel):
    total_trades: int = 0
    total_persons: int = 0
    total_subscriptions: int = 0
    total_tickers: int = 0
    uptime_seconds: float = 0
    last_pipeline_run: Optional[datetime] = None
    is_pipeline_running: bool = False
    next_pipeline_run: Optional[datetime] = None
    last_price_update: Optional[datetime] = None
    next_price_update: Optional[datetime] = None
    next_backup_run: Optional[datetime] = None
    api_status: str = "online"
    db_status: str = "connected"
    llm_status: str = "unknown"


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class LogList(BaseModel):
    logs: List[LogEntry]

# ═══════════════════════════════════════════════════════════════
# Data Source Provider Schemas
# ═══════════════════════════════════════════════════════════════

DATASOURCE_PROVIDER_FIELDS = {
    "house": {},
    "senate": {},
    "quiver": {"api_key": "Quiver API Key"},
    "sec13f": {"cik_list": "CIK List (comma-separated 10-digit numbers)"},
    "sec13d": {"cik_list": "CIK List (comma-separated 10-digit numbers)"},
    "sec_form4": {},
    "finnhub": {"api_key": "Finnhub API Key"},
    "directors_dealings": {},
    "social_inverse_cramer": {},
}

class DataSourceConfigCreate(BaseModel):
    provider_type: str = Field(description="house, senate, quiver, sec13f, sec13d, sec_form4, finnhub, directors_dealings")
    name: str
    config_json: Dict[str, Any]

class DataSourceConfigOut(BaseModel):
    id: int
    provider_type: str
    name: str
    config_json: Dict[str, Any]
    is_enabled: bool
    last_fetch: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DataSourceConfigUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None

AppSettingsOut.model_rebuild()
