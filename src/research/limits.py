"""Spending and abuse limits for the public demo. Checked before a brief starts; nothing is sent when one is hit.

- per session: MAX_BRIEFS_PER_SESSION briefs (each brief also has its own cost cap, RUN_COST_CAP_USD)
- per day, across every visitor: DAILY_BRIEF_CAP briefs and DAILY_COST_CAP_USD of model and search spend

The daily counters live in one small JSON file per day under LOG_DIR (git-ignored), written atomically. On
Streamlit Cloud the disk resets when the app restarts, so the daily counters reset too: the Anthropic Console's
monthly spend limit stays the backstop (README, Deploy).
"""

import hmac
import json
import os
import threading
from datetime import date
from pathlib import Path

from research import config

_LOCK = threading.Lock()


def _path(day: date, log_dir: Path | None = None) -> Path:
    return Path(log_dir or config.LOG_DIR) / f"usage-{day.isoformat()}.json"


def today_totals(day: date | None = None, log_dir: Path | None = None) -> dict:
    path = _path(day or date.today(), log_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"questions": 0, "cost_usd": 0.0}


def has_code(given: str, expected: str | None = None) -> bool:
    """The visitor typed the right DEMO_CODE (constant-time). No code set = nobody has it."""
    expected = config.demo_code() if expected is None else expected
    return bool(expected) and hmac.compare_digest((given or "").strip().encode(), expected.encode())


def month_cost(day: date | None = None, log_dir: Path | None = None, durable: float = 0.0) -> float:
    """This month's spend: the daily files on this disk, or the durable total from the ops log (Neon) when that is
    higher. Streamlit Cloud's disk resets on restart; the ops log doesn't, so the monthly cap survives a restart."""
    day = day or date.today()
    folder = Path(log_dir or config.LOG_DIR)
    local = 0.0
    for path in folder.glob(f"usage-{day.isoformat()[:7]}-*.json"):
        try:
            local += json.loads(path.read_text(encoding="utf-8")).get("cost_usd", 0.0)
        except (OSError, ValueError):
            continue
    return round(max(local, durable), 6)


def blocked(
    asked: int, day: date | None = None, log_dir=None, code_ok: bool = True, month_spent: float | None = None
) -> str | None:
    """A friendly reason a new brief can't start right now, or None. `code_ok=False`: a visitor without DEMO_CODE."""
    if asked >= config.MAX_BRIEFS_PER_SESSION:
        return f"This demo makes {config.MAX_BRIEFS_PER_SESSION} briefs per visit. Thanks for trying it!"
    spent = month_cost(day, log_dir) if month_spent is None else month_spent
    if spent >= config.MONTHLY_COST_CAP_USD:
        return "The demo has reached this month's spending limit. The three example briefs above are still open."
    totals = today_totals(day, log_dir)
    if totals["questions"] >= config.DAILY_BRIEF_CAP or totals["cost_usd"] >= config.DAILY_COST_CAP_USD:
        return "The demo has reached today's limit for briefs. It resets tomorrow; the README shows how to run it."
    if not code_ok and totals.get("public", 0) >= config.PUBLIC_DAILY_BRIEF_CAP:
        return (
            f"Live briefs without a demo code are limited to {config.PUBLIC_DAILY_BRIEF_CAP} a day across everyone, "
            "and today's are used. Open one of the example briefs above, or come back tomorrow."
        )
    return None


def record(
    cost: float, count: bool = True, day: date | None = None, log_dir: Path | None = None, public: bool = False
) -> dict:
    """Add a brief (count=True) or a chat turn (count=False) and its cost to today's totals. `public`: a live brief
    started without DEMO_CODE (counted against PUBLIC_DAILY_BRIEF_CAP)."""
    path = _path(day or date.today(), log_dir)
    with _LOCK:
        totals = today_totals(day, log_dir)
        totals["questions"] += 1 if count else 0
        totals["public"] = totals.get("public", 0) + (1 if count and public else 0)
        totals["cost_usd"] = round(totals["cost_usd"] + cost, 6)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(totals), encoding="utf-8")
        os.replace(tmp, path)
    return totals
