"""Settings from environment variables or Streamlit secrets (README: Configuration). Secrets have no defaults."""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _float(name: str, default: str) -> float:
    return float(os.getenv(name) or default)


LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
LLM_EFFORT = os.getenv("LLM_EFFORT", "low")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4000"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))
# The basic web search tool: the dynamic-filtering version errored on Claude Haiku 5.5 (docs/DECISIONS.md #2).
WEB_SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20250305")
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "6"))
SEARCHES_PER_QUESTION = int(os.getenv("SEARCHES_PER_QUESTION", "2"))
RUN_COST_CAP_USD = _float("RUN_COST_CAP_USD", "0.25")  # a run stops researching when it gets close to this
# Prices, USD. Defaults: Claude Haiku 5.5 list price per million tokens; web search per 1,000 searches (2026-10).
PRICE_IN_PER_M = _float("PRICE_IN_PER_M", "0.10")
PRICE_OUT_PER_M = _float("PRICE_OUT_PER_M", "0.50")
PRICE_PER_1K_SEARCHES = _float("PRICE_PER_1K_SEARCHES", "10")
CACHE_DIR = Path(os.getenv("CACHE_DIR", ROOT / "data" / "cache"))
USER_AGENT = "fde-account-research-agent/1.0 (+https://github.com/vamsialladev/fde-account-research-agent)"
FETCH_TIMEOUT_S = float(os.getenv("FETCH_TIMEOUT_S", "10"))
FETCH_MAX_BYTES = int(os.getenv("FETCH_MAX_BYTES", "2000000"))
STALE_AFTER_DAYS = 365
MAX_BRIEFS_PER_SESSION = int(os.getenv("MAX_BRIEFS_PER_SESSION", "3"))
DAILY_BRIEF_CAP = int(os.getenv("DAILY_BRIEF_CAP", "30"))
DAILY_COST_CAP_USD = _float("DAILY_COST_CAP_USD", "3.00")
# Every brief uses paid web search, so the public demo is gated (final plan, step 8): visitors open three saved
# example briefs for free; live runs need DEMO_CODE, or are limited to PUBLIC_DAILY_BRIEF_CAP a day across everyone;
# MONTHLY_COST_CAP_USD stops all live runs for the rest of the month.
PUBLIC_DAILY_BRIEF_CAP = int(os.getenv("PUBLIC_DAILY_BRIEF_CAP", "3"))
MONTHLY_COST_CAP_USD = _float("MONTHLY_COST_CAP_USD", "10.00")


def demo_code() -> str:
    """Read at call time (a secret added on Streamlit Cloud is picked up). Never logged or shown."""
    value = os.getenv("DEMO_CODE", "")
    if value:
        return value.strip()
    try:
        import streamlit as st

        return str(st.secrets.get("DEMO_CODE", "")).strip()
    except Exception:  # noqa: BLE001 - no secrets file outside Streamlit
        return ""


LOG_DIR = Path(os.getenv("LOG_DIR", ROOT / "logs"))
DEMO_VIDEO_URL = os.getenv("DEMO_VIDEO_URL", "")
REPO_URL = "https://github.com/vamsialladev/fde-account-research-agent"
PORTFOLIO_URL = "https://vamsialla.com"


def today() -> date:
    pinned = os.getenv("RESEARCH_TODAY", "")
    return date.fromisoformat(pinned) if pinned else date.today()
