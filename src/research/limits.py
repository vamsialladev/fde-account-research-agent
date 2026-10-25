"""Spending and abuse limits for the public demo. Checked before a brief starts; nothing is sent when one is hit.

- per session: MAX_BRIEFS_PER_SESSION briefs (each brief also has its own cost cap, RUN_COST_CAP_USD)
- per day, across every visitor: DAILY_BRIEF_CAP briefs and DAILY_COST_CAP_USD of model and search spend

The daily counters live in one small JSON file per day under LOG_DIR (git-ignored), written atomically. On
Streamlit Cloud the disk resets when the app restarts, so the daily counters reset too: the Anthropic Console's
monthly spend limit stays the backstop (README, Deploy).
"""

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


def blocked(asked: int, day: date | None = None, log_dir=None) -> str | None:
    """A friendly reason a new brief can't start right now, or None."""
    if asked >= config.MAX_BRIEFS_PER_SESSION:
        return f"This demo makes {config.MAX_BRIEFS_PER_SESSION} briefs per visit. Thanks for trying it!"
    totals = today_totals(day, log_dir)
    if totals["questions"] >= config.DAILY_BRIEF_CAP or totals["cost_usd"] >= config.DAILY_COST_CAP_USD:
        return "The demo has reached today's limit for briefs. It resets tomorrow; the README shows how to run it."
    return None


def record(cost: float, count: bool = True, day: date | None = None, log_dir: Path | None = None) -> dict:
    """Add a brief (count=True) or a chat turn (count=False) and its cost to today's totals."""
    path = _path(day or date.today(), log_dir)
    with _LOCK:
        totals = today_totals(day, log_dir)
        totals["questions"] += 1 if count else 0
        totals["cost_usd"] = round(totals["cost_usd"] + cost, 6)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(totals), encoding="utf-8")
        os.replace(tmp, path)
    return totals
