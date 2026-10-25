"""Business case calculator for the account research agent: prep time saved before first client meetings. Every
input is an assumption (docs/BUSINESS_CASE.md says why) except the AI cost per brief, which is measured; the result
is a projection, not a measurement.

    python scripts/business_case.py               # base case, a team of 8
    python scripts/business_case.py --scenarios   # pessimistic / base / optimistic table
    python scripts/business_case.py --team 40 --scenarios --cost-per-brief 0.14
"""

import argparse
import sys
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Assumptions:
    first_meetings_per_engineer_month: float = 4.0  # new accounts or new stakeholders researched from scratch
    manual_prep_hours: float = 2.5  # reading the website, filings, news and reviews, writing notes and questions
    share_of_prep_replaced: float = 0.40  # the brief replaces the gathering, not the thinking
    review_minutes: float = 15.0  # checking the brief's sources before using it
    loaded_cost_per_hour: float = 95.0
    briefs_per_meeting: float = 1.5  # some accounts are researched twice (before and after a first call)
    ai_cost_per_brief: float = 0.14  # measured: research eval 2026-10-25 (see README Results)
    hosting_per_month: float = 25.0


SCENARIOS = {
    "pessimistic": dict(first_meetings_per_engineer_month=2.0, share_of_prep_replaced=0.20, review_minutes=25.0),
    "base": {},
    "optimistic": dict(first_meetings_per_engineer_month=6.0, share_of_prep_replaced=0.55, review_minutes=10.0),
}


def per_year(a: Assumptions, team: int) -> dict:
    meetings = a.first_meetings_per_engineer_month * 12 * team
    hours_saved = meetings * (a.manual_prep_hours * a.share_of_prep_replaced - a.review_minutes / 60)
    time_value = hours_saved * a.loaded_cost_per_hour
    ai = meetings * a.briefs_per_meeting * a.ai_cost_per_brief
    hosting = a.hosting_per_month * 12
    return {
        "first meetings": meetings,
        "hours saved": hours_saved,
        "time saved ($)": time_value,
        "AI cost": ai,
        "hosting": hosting,
        "net value": time_value - ai - hosting,
    }


def money(v: float) -> str:
    return f"-${-v:,.0f}" if v < 0 else f"${v:,.0f}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--team", type=int, default=8, help="engineers who run first meetings")
    p.add_argument("--scenarios", action="store_true")
    p.add_argument("--cost-per-brief", type=float, default=None, help="measured AI cost per brief (USD)")
    args = p.parse_args(argv)
    base = Assumptions() if args.cost_per_brief is None else Assumptions(ai_cost_per_brief=args.cost_per_brief)
    names = list(SCENARIOS) if args.scenarios else ["base"]
    results = {n: per_year(replace(base, **SCENARIOS[n]), args.team) for n in names}
    print(f"Projection per year, a team of {args.team} (assumptions, not measurements)\n")
    print("| Line | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for key in results[names[0]]:
        counts = key in ("first meetings", "hours saved")
        cells = [f"{results[n][key]:,.0f}" if counts else money(results[n][key]) for n in names]
        print(f"| {key} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
