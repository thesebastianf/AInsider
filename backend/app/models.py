"""
AInsider Tracker – SQLAlchemy ORM Models
Defines TargetPerson, Trade, AssetPerformance, Subscription,
LLMConfig, and NotificationConfig.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, Date, DateTime,
    ForeignKey, JSON, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TargetPerson(Base):
    """A tracked individual (Congress member, Senator, Fund Manager)."""
    __tablename__ = "target_persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False)  # "Congress", "Senate", "Fund Manager"
    committee_affiliations = Column(JSON, default=list)
    photo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    is_followed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trades = relationship("Trade", back_populates="person", lazy="dynamic",
                          order_by="Trade.trade_date.desc()")
    subscriptions = relationship("Subscription", back_populates="person")

    def __repr__(self):
        return f"<TargetPerson(id={self.id}, name='{self.name}', category='{self.category}')>"


class Trade(Base):
    """A single stock trade filing by a tracked person."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    target_person_id = Column(Integer, ForeignKey("target_persons.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    type = Column(String(4), nullable=False)  # "BUY" or "SELL"
    amount_range = Column(String(50), nullable=False)  # e.g., "$100k-$250k"
    trade_date = Column(Date, nullable=False)
    filing_date = Column(Date)
    source_url = Column(String(500))
    ai_score = Column(Integer)  # 1-10, NULL if not yet evaluated
    ai_summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Deduplication constraint
    __table_args__ = (
        UniqueConstraint(
            "target_person_id", "ticker", "trade_date", "amount_range",
            name="uq_trade_dedup"
        ),
    )

    # Relationships
    person = relationship("TargetPerson", back_populates="trades")

    def __repr__(self):
        return f"<Trade(id={self.id}, ticker='{self.ticker}', type='{self.type}')>"


class AssetPerformance(Base):
    """Tracks current price and YTD performance for a stock ticker."""
    __tablename__ = "asset_performance"

    ticker = Column(String(10), primary_key=True)
    current_price = Column(Float)
    ytd_performance_pct = Column(Float)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AssetPerformance(ticker='{self.ticker}', price={self.current_price})>"


class Subscription(Base):
    """User subscription to a TargetPerson for notifications."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), default="default", nullable=False)
    target_person_id = Column(Integer, ForeignKey("target_persons.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    person = relationship("TargetPerson", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, person_id={self.target_person_id})>"


class LLMConfig(Base):
    """LLM provider configuration (stored in DB, UI-editable)."""
    __tablename__ = "llm_config"

    id = Column(Integer, primary_key=True, index=True)
    provider_type = Column(String(50), nullable=False)  # "ollama", "openai", "anthropic", "custom"
    name = Column(String(100), nullable=False)  # Display name
    api_url = Column(String(500), nullable=False)  # Endpoint URL
    api_key = Column(String(500))  # API key (nullable for Ollama)
    model_name = Column(String(100), nullable=False)  # e.g., "llama3", "gpt-4o-mini"
    is_active = Column(Boolean, default=False, nullable=False)  # Only one should be active
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<LLMConfig(id={self.id}, provider='{self.provider_type}', model='{self.model_name}')>"


class NotificationConfig(Base):
    """Notification provider configuration (stored in DB, UI-editable)."""
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True, index=True)
    provider_type = Column(String(50), nullable=False)
    # Provider types: "telegram", "gotify", "pushover", "discord", "slack", "ntfy"
    name = Column(String(100), nullable=False)  # Display name
    config_json = Column(JSON, nullable=False, default=dict)
    # Config fields per provider:
    #   telegram: { bot_token, chat_id }
    #   gotify:   { url, app_token }
    #   pushover: { user_key, api_token }
    #   discord:  { webhook_url }
    #   slack:    { webhook_url }
    #   ntfy:     { url, topic, token? }
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_test = Column(DateTime)  # Last successful test timestamp
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<NotificationConfig(id={self.id}, provider='{self.provider_type}', enabled={self.is_enabled})>"


class DataSourceConfig(Base):
    """Data source provider configuration (stored in DB, UI-editable)."""
    __tablename__ = "datasource_config"

    id = Column(Integer, primary_key=True, index=True)
    provider_type = Column(String(50), nullable=False)
    # Provider types: "house", "senate", "quiver", "sec13f"
    name = Column(String(100), nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)
    # Config fields e.g., { "api_key": "..." } for Quiver
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_fetch = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<DataSourceConfig(id={self.id}, provider='{self.provider_type}', enabled={self.is_enabled})>"
