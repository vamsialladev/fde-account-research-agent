"""Three example briefs any visitor can open without a live run (and without spending anything).

They're real briefs from the saved 2026-10-25 eval run (scripts/make_examples.py copies them as they were saved), so
the page labels them with that date: company facts change, and these aren't refreshed.
"""

import json
from functools import lru_cache

from research import config
from research.models import Finding, Source, Usage
from research.pipeline import Run

FOLDER = config.ROOT / "data" / "examples"
ORDER = ("hyatt-hotels-corporation", "club-med", "four-seasons-hotels-and-resorts")
SAVED_ON = "2026-10-25"


@lru_cache(maxsize=1)
def load() -> dict:
    """{company: example dict}, in the order shown on the page."""
    out = {}
    for name in ORDER:
        path = FOLDER / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            out[data["company"]] = data
    return out


def to_run(example: dict) -> Run:
    """The saved brief as a Run, so the page's brief view, chat and share link work on it unchanged."""
    findings = [
        Finding(f["id"], f["topic"], f["claim"], [Source(**s) for s in f.get("sources", [])], list(f.get("flags", [])))
        for f in example["findings"]
    ]
    run = Run(example["company"], findings=findings, markdown=example["markdown"], seconds=example["seconds"])
    run.critic = {"quotes_found": example["quotes_found"], "quotes_checked": example["quotes_checked"]}
    run.usage = Usage(example["tokens_in"], example["tokens_out"], example["searches"])
    return run
