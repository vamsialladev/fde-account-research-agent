"""Copy the three example briefs a visitor can open without a live run, from a saved eval run.

    python scripts/make_examples.py

Source: eval/reports/research-2026-10-25-dev.jsonl, run 1 of Hyatt Hotels Corporation, Club Med and Four Seasons
Hotels and Resorts (each passed every check in that run). The brief, its findings and its numbers are copied as they
were saved; nothing is rewritten. tests/test_examples.py fails if a file drifts from its source record.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "eval" / "reports" / "research-2026-10-25-dev.jsonl"
OUT = ROOT / "data" / "examples"
COMPANIES = ("Hyatt Hotels Corporation", "Club Med", "Four Seasons Hotels and Resorts")
FIELDS = ("company", "run", "markdown", "findings", "quotes_found", "quotes_checked", "coverage", "seconds",
          "tokens_in", "tokens_out", "searches")  # fmt: skip


def slug(company: str) -> str:
    return "-".join(company.lower().split())


def records() -> dict:
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["company"]: r for r in rows if r["company"] in COMPANIES and r["run"] == 1}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for company, r in records().items():
        example = {k: r[k] for k in FIELDS}
        example["source"] = f"{SOURCE.relative_to(ROOT).as_posix()} (run {r['run']})"
        (OUT / f"{slug(company)}.json").write_text(json.dumps(example, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote data/examples/{slug(company)}.json")


if __name__ == "__main__":
    main()
