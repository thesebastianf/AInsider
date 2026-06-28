"""
AInsider Tracker – LLM Provider Abstraction
Strategy pattern for multiple LLM backends:
  - Ollama (local)
  - OpenAI (GPT-4o, GPT-4o-mini, etc.)
  - Anthropic (Claude)
  - Generic OpenAI-compatible (LM Studio, vLLM, LocalAI, etc.)
"""

import json
import logging
import re
from typing import Tuple, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import LLMConfig

logger = logging.getLogger("ainsider.llm")

# ═══════════════════════════════════════════════════════════════
# Prompt Builder
# ═══════════════════════════════════════════════════════════════

def _build_prompt(person_name: str, committees: list, trade_type: str,
                  ticker: str, amount: str) -> str:
    """Build the evaluation prompt."""
    committees_str = ", ".join(committees) if committees else "Unknown"
    return (
        f"Evaluate this stock trade by a political figure for potential insider trading risk.\n\n"
        f"Person: {person_name}\n"
        f"Committees: {committees_str}\n"
        f"Action: {trade_type} {ticker}\n"
        f"Volume: {amount}\n\n"
        f"Based on this person's committee assignments and the stock traded, "
        f"does this person likely have insider knowledge relevant to this trade?\n\n"
        f"Respond ONLY with valid JSON in this exact format:\n"
        f'{{"score": <integer 1-10>, "summary": "<2-sentence summary>"}}\n\n'
        f"Where score 1 = very low risk, 10 = very high insider risk."
    )


# ═══════════════════════════════════════════════════════════════
# Response Parser
# ═══════════════════════════════════════════════════════════════

def _parse_response(text: str) -> Tuple[int, str]:
    """Parse the AI response to extract score and summary."""
    # Try parsing as JSON first
    try:
        json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            score = max(1, min(10, int(data.get("score", 5))))
            summary = str(data.get("summary", "No summary available."))
            return score, summary
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    # Fallback: extract score from text
    score_match = re.search(r'(?:score|risk)[:\s]*(\d+)', text, re.IGNORECASE)
    score = max(1, min(10, int(score_match.group(1)))) if score_match else 5

    sentences = re.split(r'[.!]', text)
    summary = ". ".join(s.strip() for s in sentences[:2] if s.strip())
    if not summary:
        summary = "AI evaluation completed but response format was unexpected."

    return score, summary[:500]


# ═══════════════════════════════════════════════════════════════
# Provider Implementations
# ═══════════════════════════════════════════════════════════════

def _call_ollama(config: LLMConfig, prompt: str) -> str:
    """Call Ollama API."""
    resp = httpx.post(
        f"{config.api_url.rstrip('/')}/api/generate",
        json={
            "model": config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 200},
        },
        timeout=90.0,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _call_openai_compatible(config: LLMConfig, prompt: str) -> str:
    """Call OpenAI-compatible API (works for OpenAI, custom gateways, LM Studio, etc.)."""
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    url = config.api_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/v1/chat/completions"

    resp = httpx.post(
        url,
        json={
            "model": config.model_name,
            "messages": [
                {"role": "system", "content": "You are a financial analyst evaluating stock trades for insider trading risk. Always respond with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
        },
        headers=headers,
        timeout=90.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_anthropic(config: LLMConfig, prompt: str) -> str:
    """Call Anthropic Claude API."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key or "",
        "anthropic-version": "2023-06-01",
    }

    url = config.api_url.rstrip("/")
    if not url.endswith("/messages"):
        url = f"{url}/v1/messages"

    resp = httpx.post(
        url,
        json={
            "model": config.model_name,
            "max_tokens": 200,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "system": "You are a financial analyst evaluating stock trades for insider trading risk. Always respond with valid JSON.",
        },
        headers=headers,
        timeout=90.0,
    )
    resp.raise_for_status()
    data = resp.json()
    # Anthropic returns content as list of blocks
    content_blocks = data.get("content", [])
    return content_blocks[0]["text"] if content_blocks else ""


# Provider dispatch
_PROVIDERS = {
    "ollama": _call_ollama,
    "openai": _call_openai_compatible,
    "anthropic": _call_anthropic,
    "custom": _call_openai_compatible,  # Custom gateways use OpenAI-compatible format
}


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def get_active_llm_config(db: Session) -> Optional[LLMConfig]:
    """Get the currently active LLM configuration."""
    return db.query(LLMConfig).filter(LLMConfig.is_active == True).first()  # noqa: E712


def evaluate_trade(
    db: Session,
    person_name: str,
    committees: list,
    trade_type: str,
    ticker: str,
    amount: str,
) -> Tuple[int, str]:
    """
    Evaluate a trade using the active LLM provider.
    Returns: (score: 1-10, summary: str)
    """
    config = get_active_llm_config(db)
    if not config:
        logger.warning("No active LLM provider configured")
        return 0, "No AI provider configured. Set up an LLM provider in Settings."

    prompt = _build_prompt(person_name, committees, trade_type, ticker, amount)
    provider_fn = _PROVIDERS.get(config.provider_type)

    if not provider_fn:
        logger.error(f"Unknown LLM provider type: {config.provider_type}")
        return 0, f"Unknown LLM provider: {config.provider_type}"

    try:
        text = provider_fn(config, prompt)
        logger.info(f"LLM response for {ticker}: {text[:100]}...")
        return _parse_response(text)
    except httpx.TimeoutException:
        logger.warning(f"LLM timeout for {person_name}/{ticker}")
        return 0, "AI evaluation timed out. Check your provider settings."
    except httpx.ConnectError:
        logger.warning(f"LLM provider not reachable: {config.api_url}")
        return 0, "AI service unavailable. Check provider URL and status."
    except Exception as e:
        logger.error(f"LLM evaluation failed: {e}")
        return 0, f"AI evaluation error: {str(e)[:100]}"


def test_llm_connection(config: LLMConfig) -> Tuple[bool, str, Optional[str]]:
    """
    Test connectivity to an LLM provider.
    Returns: (success, message, raw_response)
    """
    prompt = "Respond with exactly this JSON: {\"score\": 5, \"summary\": \"Test successful.\"}"
    provider_fn = _PROVIDERS.get(config.provider_type)

    if not provider_fn:
        return False, f"Unknown provider type: {config.provider_type}", None

    try:
        text = provider_fn(config, prompt)
        return True, f"Connection successful! Model: {config.model_name}", text[:200]
    except httpx.ConnectError:
        return False, f"Cannot connect to {config.api_url}. Is the service running?", None
    except httpx.TimeoutException:
        return False, "Connection timed out. The model may be loading.", None
    except httpx.HTTPStatusError as e:
        return False, f"HTTP error {e.response.status_code}: {e.response.text[:100]}", None
    except Exception as e:
        return False, f"Error: {str(e)[:150]}", None
