"""
AInsider Tracker – Notification Engine
Multi-provider notification dispatcher.
Providers: Telegram, Gotify, Pushover, Discord, Slack, Ntfy.
All configured via DB (UI-editable).
"""

import logging
from typing import Dict, List

import httpx
from sqlalchemy.orm import Session

from app.models import NotificationConfig, Subscription, TargetPerson

logger = logging.getLogger("ainsider.notifier")


# ═══════════════════════════════════════════════════════════════
# Message Formatter
# ═══════════════════════════════════════════════════════════════

def _format_message(
    person_name: str, trade_type: str, ticker: str,
    amount: str, ai_score: int, ai_summary: str,
) -> str:
    action_emoji = "📈" if trade_type == "BUY" else "📉"
    return (
        f"🚨 [AI]nsider Alert\n\n"
        f"👤 {person_name}\n"
        f"{action_emoji} {trade_type} {ticker}\n"
        f"💰 {amount}\n\n"
        f"🧠 AI Score: {ai_score}/10\n"
        f"📝 {ai_summary}"
    )


# ═══════════════════════════════════════════════════════════════
# Provider Implementations
# ═══════════════════════════════════════════════════════════════

def _send_telegram(config: dict, title: str, message: str) -> bool:
    token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not token or not chat_id:
        return False
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_gotify(config: dict, title: str, message: str) -> bool:
    url = config.get("url", "").rstrip("/")
    token = config.get("app_token", "")
    if not url or not token:
        return False
    resp = httpx.post(
        f"{url}/message",
        json={"title": title, "message": message, "priority": 5},
        headers={"X-Gotify-Key": token},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_pushover(config: dict, title: str, message: str) -> bool:
    user_key = config.get("user_key", "")
    api_token = config.get("api_token", "")
    if not user_key or not api_token:
        return False
    resp = httpx.post(
        "https://api.pushover.net/1/messages.json",
        data={"token": api_token, "user": user_key, "title": title, "message": message},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_discord(config: dict, title: str, message: str) -> bool:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False
    resp = httpx.post(
        webhook_url,
        json={"content": f"**{title}**\n{message}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_slack(config: dict, title: str, message: str) -> bool:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False
    resp = httpx.post(
        webhook_url,
        json={"text": f"*{title}*\n{message}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_ntfy(config: dict, title: str, message: str) -> bool:
    url = config.get("url", "https://ntfy.sh").rstrip("/")
    topic = config.get("topic", "")
    token = config.get("token")
    if not topic:
        return False
    headers = {"Title": title}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.post(f"{url}/{topic}", content=message, headers=headers, timeout=10.0)
    resp.raise_for_status()
    return True


# Provider dispatch table
_SENDERS = {
    "telegram": _send_telegram,
    "gotify": _send_gotify,
    "pushover": _send_pushover,
    "discord": _send_discord,
    "slack": _send_slack,
    "ntfy": _send_ntfy,
}


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def send_notification(provider_config: NotificationConfig, title: str, message: str) -> bool:
    """Send a notification via a specific provider config."""
    sender = _SENDERS.get(provider_config.provider_type)
    if not sender:
        logger.error(f"Unknown notification provider: {provider_config.provider_type}")
        return False
    try:
        return sender(provider_config.config_json or {}, title, message)
    except Exception as e:
        logger.error(f"Notification via {provider_config.name} failed: {e}")
        return False


def test_notification(provider_config: NotificationConfig) -> tuple[bool, str]:
    """Send a test notification."""
    title = "🧪 AInsider Test"
    message = "This is a test notification from AInsider Tracker. If you see this, your notification provider is configured correctly! ✅"
    try:
        success = send_notification(provider_config, title, message)
        if success:
            return True, "Test notification sent successfully!"
        return False, "Failed to send test notification. Check your credentials."
    except Exception as e:
        return False, f"Error: {str(e)[:150]}"


def notify_all_enabled(
    db: Session,
    person_name: str,
    trade_type: str,
    ticker: str,
    amount: str,
    ai_score: int,
    ai_summary: str,
) -> Dict[str, bool]:
    """
    Send notifications to ALL enabled providers.
    Returns dict with provider names and success status.
    """
    message = _format_message(person_name, trade_type, ticker, amount, ai_score, ai_summary)
    title = f"🚨 {person_name} {trade_type} {ticker}"

    configs = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.is_enabled == True)  # noqa: E712
        .all()
    )

    results = {}
    for cfg in configs:
        success = send_notification(cfg, title, message)
        results[cfg.name] = success
        if success:
            logger.info(f"Notification sent via {cfg.name} ({cfg.provider_type})")
        else:
            logger.warning(f"Notification failed for {cfg.name} ({cfg.provider_type})")

    return results
