"""
AInsider Tracker – Hot Stocks Alerts
Sends a notification when a ticker newly enters the Top-N of the
"Most traded" (Hot Stocks) or "Multi-buyer" (co-buying clusters) rankings.

The previous Top-N is persisted to a small JSON file so a container restart
doesn't re-alert the whole list. On the very first run the current lists are
stored as the baseline without alerting.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Trade

logger = logging.getLogger("ainsider.hot_alerts")

INVALID_TICKERS = ["NONE", "NONE.", "N/A", "NA", "NULL", "UNKNOWN", ""]
WINDOW_DAYS = 60
# A ticker hovering around rank N would otherwise alert every time it re-enters
REALERT_COOLDOWN_DAYS = 7


def top_traded(db: Session, limit: int) -> list:
    """Most traded tickers in the last 60 days (same ranking as the Hot Stocks widget)."""
    cutoff = date.today() - timedelta(days=WINDOW_DAYS)
    return (
        db.query(
            Trade.ticker,
            func.count(Trade.id).label("trade_count"),
            func.sum(case((Trade.type == "BUY", 1), else_=0)).label("buy_count"),
            func.sum(case((Trade.type == "SELL", 1), else_=0)).label("sell_count"),
            func.count(distinct(Trade.target_person_id)).label("distinct_persons"),
            func.max(Trade.trade_date).label("last_trade_date"),
        )
        .filter(
            Trade.trade_date >= cutoff,
            Trade.ticker.isnot(None),
            ~Trade.ticker.in_(INVALID_TICKERS),
        )
        .group_by(Trade.ticker)
        .order_by(func.count(Trade.id).desc())
        .limit(limit)
        .all()
    )


def _top_multi_buyer(db: Session, limit: int) -> list:
    """Tickers with 2+ distinct buyers in the last 60 days (same ranking as the Clusters view)."""
    from app.routers.trades import get_clusters

    return get_clusters(days=WINDOW_DAYS, min_buyers=2, db=db).clusters[:limit]


def _load_state(path: str) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"Could not read hot stocks state ({e}), starting a new baseline")
        return None


def _save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Could not save hot stocks state: {e}")


def check_hot_stock_entries(db: Session) -> int:
    """Alert on tickers that newly entered a Top-N ranking. Returns number of new entries alerted."""
    from app.routers.system import add_log
    from app.services.notifier import notify_system_event

    if not settings.NOTIFY_HOT_STOCKS:
        return 0

    top_n = settings.HOT_STOCKS_TOP_N
    traded = top_traded(db, top_n)
    multi = _top_multi_buyer(db, top_n)
    current = {
        "most_traded": [row.ticker for row in traded],
        "multi_buyer": [c.ticker for c in multi],
    }

    path = settings.HOT_STOCKS_STATE_FILE
    state = _load_state(path)
    if state is None:
        _save_state(path, {**current, "alerted": {}})
        add_log("INFO", f"Hot stocks alert baseline stored (Top {top_n})")
        return 0

    now = datetime.now()
    alerted = {
        key: ts for key, ts in state.get("alerted", {}).items()
        if now - datetime.fromisoformat(ts) < timedelta(days=REALERT_COOLDOWN_DAYS)
    }

    lines = []
    new_count = 0
    for rank, row in enumerate(traded, 1):
        key = f"most_traded:{row.ticker}"
        if row.ticker in state.get("most_traded", []) or key in alerted:
            continue
        lines.append(
            f"🔥 Most traded #{rank}: {row.ticker} · {row.trade_count} trades "
            f"({int(row.buy_count or 0)} buy / {int(row.sell_count or 0)} sell) · "
            f"{int(row.distinct_persons or 0)} persons"
        )
        alerted[key] = now.isoformat()
        new_count += 1

    for rank, c in enumerate(multi, 1):
        key = f"multi_buyer:{c.ticker}"
        if c.ticker in state.get("multi_buyer", []) or key in alerted:
            continue
        buyers = ", ".join(c.buyer_names[:5])
        if len(c.buyer_names) > 5:
            buyers += f" +{len(c.buyer_names) - 5}"
        lines.append(
            f"👥 Multi-buyer #{rank}: {c.ticker} · {c.distinct_buyers_count} buyers ({buyers})"
        )
        alerted[key] = now.isoformat()
        new_count += 1

    _save_state(path, {**current, "alerted": alerted})

    if lines:
        message = f"🚨 [AI]nsider Hot Stocks\n\nNew in the Top {top_n} (last {WINDOW_DAYS} days):\n\n" + "\n".join(lines)
        notify_system_event(db, f"🔥 New Hot Stocks entries ({new_count})", message)
        add_log("INFO", f"Sent hot stocks alert for {new_count} new Top {top_n} entries")
    return new_count
