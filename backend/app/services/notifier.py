"""
AInsider Tracker – Notification Engine
Multi-provider notification dispatcher.
Providers: Telegram, Gotify, Pushover, Discord, Slack, Ntfy.
All configured via DB (UI-editable).
"""

import html
import logging
import threading
import time
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
    trade_date: str = "",
) -> str:
    action_emoji = "📈" if trade_type == "BUY" else "📉"
    date_str = f"📅 {trade_date}\n" if trade_date else ""
    
    # If LLM is not configured, AI score is 0 and summary is empty
    ai_section = ""
    if ai_summary:
        ai_section = f"🧠 AI Score: {ai_score}/10\n📝 {ai_summary}"
    else:
        ai_section = "🤖 AI enrichment unavailable (check settings)"
        
    return (
        f"🚨 [AI]nsider Alert\n\n"
        f"👤 {person_name}\n"
        f"{action_emoji} {trade_type} {ticker}\n"
        f"{date_str}"
        f"💰 {amount}\n\n"
        f"{ai_section}"
    )


# ═══════════════════════════════════════════════════════════════
# Provider Implementations
# ═══════════════════════════════════════════════════════════════

# Telegram allows ~1 message/second per chat and caps a message at 4096 chars.
TELEGRAM_MAX_LEN = 4096
TELEGRAM_MIN_INTERVAL_S = 1.1
TELEGRAM_MAX_RETRY_AFTER_S = 60
_telegram_lock = threading.Lock()
_telegram_last_sent = 0.0


def _send_telegram(config: dict, title: str, message: str) -> bool:
    global _telegram_last_sent
    token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not token or not chat_id:
        return False

    # Messages are sent with parse_mode=HTML, so raw text (AI summaries, company
    # names like "S&P 500" or "AT&T", "<5%") must be escaped, otherwise Telegram
    # rejects the whole message with "can't parse entities".
    text = html.escape(message, quote=False)
    if len(text) > TELEGRAM_MAX_LEN:
        text = text[: TELEGRAM_MAX_LEN - 1] + "…"

    with _telegram_lock:
        for attempt in range(3):
            wait = TELEGRAM_MIN_INTERVAL_S - (time.monotonic() - _telegram_last_sent)
            if wait > 0:
                time.sleep(wait)
            resp = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10.0,
            )
            _telegram_last_sent = time.monotonic()
            if resp.status_code == 429 and attempt < 2:
                try:
                    retry_after = int(resp.json().get("parameters", {}).get("retry_after", 5))
                except Exception:
                    retry_after = 5
                logger.warning(f"Telegram rate limit hit, retrying in {retry_after}s")
                time.sleep(min(retry_after, TELEGRAM_MAX_RETRY_AFTER_S))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Telegram API {resp.status_code}: {resp.text[:200]}")
            return True
    return False


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
        try:
            from app.routers.system import add_log
            add_log("WARN", f"Notification via {provider_config.name} failed: {str(e)[:150]}")
        except Exception:
            pass
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
    trade_date: str = "",
) -> Dict[str, bool]:
    """
    Send notifications to ALL enabled providers.
    Returns dict with provider names and success status.
    """
    message = _format_message(person_name, trade_type, ticker, amount, ai_score, ai_summary, trade_date)
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


def notify_digest(db: Session, person_name: str, trades: List[dict]) -> Dict[str, bool]:
    """
    Send ONE summary notification for many new trades of the same person
    (e.g. a 13F holdings snapshot with 100+ positions) instead of flooding
    every provider with one message per trade.
    Each trade dict has: trade_type, ticker, amount, ai_score, trade_date.
    """
    max_lines = 20
    lines = []
    for t in trades[:max_lines]:
        emoji = "📈" if t["trade_type"] == "BUY" else "📉"
        score = f" · AI {t['ai_score']}/10" if t.get("ai_score") else ""
        date_part = f" · {t['trade_date']}" if t.get("trade_date") else ""
        lines.append(f"{emoji} {t['trade_type']} {t['ticker']} · {t['amount']}{date_part}{score}")
    if len(trades) > max_lines:
        lines.append(f"… and {len(trades) - max_lines} more (see app)")

    title = f"🚨 {person_name}: {len(trades)} new trades"
    message = (
        f"🚨 [AI]nsider Alert\n\n"
        f"👤 {person_name}\n"
        f"📦 {len(trades)} new trades\n\n" + "\n".join(lines)
    )

    configs = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.is_enabled == True)  # noqa: E712
        .all()
    )
    results = {}
    for cfg in configs:
        results[cfg.name] = send_notification(cfg, title, message)
    return results


def notify_system_event(db: Session, title: str, message: str) -> None:
    """
    Send a system-level notification (e.g. rate limit warnings) to all enabled providers.
    """
    configs = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.is_enabled == True)  # noqa: E712
        .all()
    )
    for cfg in configs:
        send_notification(cfg, title, message)
