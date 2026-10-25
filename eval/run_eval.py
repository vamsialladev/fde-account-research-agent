"""Eval for the research agent: real companies and fictional ones, 3 runs each, deterministic checks per brief.

python -m eval.run_eval --runs 3 --price-in 0.1 --price-out 0.5 --price-search 10        # dev
python -m eval.run_eval --split heldout --runs 3 --price-in 0.1 --price-out 0.5 --price-search 10
python -m eval.run_eval --rescore eval/reports/research-<date>-dev.jsonl                  # re-grade, no API
python -m eval.run_eval --rescore <report>.jsonl --write --price-in 0.1 --price-out 0.5 --price-search 10  # save it
python -m eval.run_eval --sample eval/reports/research-<date>-dev.jsonl                  # claims for hand labels

Checks per brief (no model):
- sourced: every brief line cites a numbered source (lines that don't are dropped before the brief is written)
- coverage: research sentences that came with a source / all research sentences (the rest are removed)
- quotes found: cited quotes found on their own page (robots.txt and unreachable pages are not counted)
- fictional companies: no facts about them; the brief says no reliable public information was found
- structure: 10 meeting questions, 3 use-case hypotheses with the 4-check, an email under 150 words, no hype
- no personal data: no email address or phone number anywhere in the brief
- no title in the email: the outreach email doesn't describe the sender ("I'm a ... engineer"); it's signed "Vamsi"
Prices are flags, never hard-coded. The unsupported-claim rate needs a person: --sample writes claims to label.
"""

import argparse
import csv
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
sys.path.insert(0, str(HERE.parent / "src"))

from research import config  # noqa: E402

HYPE = re.compile(r"\b(revolutionary|seamless|cutting-edge|leverage|game-chang|synerg|world-class|best-in-class)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SENDER_ROLE = re.compile(
    r"\b(?:I'm|I am|I work as)\s+(?:Vamsi,?\s+)?an?\s+[^.!?\n]{0,40}?"
    r"\b(?:engineer|developer|consultant|founder|architect)",
    re.I,
)
PHONE = re.compile(r"(?<![\w$.,])\+?\d{1,3}[ -]?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}(?![\w.,]?\d)")


def load(split: str) -> list[dict]:
    rows = [
        json.loads(line) for line in (HERE / "companies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return [r for r in rows if split == "all" or r["split"] == split]


NO_INFO = re.compile(r"no reliable public information", re.I)
OTHER_ENTITY = re.compile(
    r"(?:different|separate) (?:kind of )?(?:entit|compan|business)|(?:does not|doesn't|don't|do not) match|unrelated",
    re.I,
)


def email_text(md: str) -> str:
    return md.split("## Outreach email", 1)[-1].split("## Sources", 1)[0] if "## Outreach email" in md else ""


def fact_texts(body: str) -> list[str]:
    """The research lines of a brief (snapshot to tech hints), without the "Nothing reliable found." filler."""
    research = body.split("## Snapshot", 1)[-1].split("## Ten questions", 1)[0]
    lines = [line[2:] for line in research.splitlines() if line.startswith("- ")]
    return [line for line in lines if not line.startswith("Nothing reliable found")]


def honest_about_nothing(line: str) -> bool:
    """For a company that doesn't exist, a line may only say nothing was found, or that a match is someone else."""
    return bool(NO_INFO.search(line) or OTHER_ENTITY.search(line))


def grade(case: dict, out: dict) -> dict:
    """Pure: the case and a saved brief -> {check: passed}."""
    md = out["markdown"]
    checks = {
        "sourced": out["uncited_lines"] == 0,
        "structure": out["questions"] == 10 and out["use_cases"] == 3 and 0 < out["email_words"] <= 150,
        "no_hype": not HYPE.search(out["brief_body"]),  # the agent's words; a cited page's title may say "seamless"
        "no_personal_data": not EMAIL.search(md) and not PHONE.search(out["brief_body"]),
        "email_no_title": not SENDER_ROLE.search(email_text(md)),
    }
    if case["fictional"]:
        lines = fact_texts(out["brief_body"])
        checks["fictional_honest"] = bool(NO_INFO.search(md)) and all(honest_about_nothing(x) for x in lines)
    else:
        checks["has_findings"] = out["fact_lines"] >= 3
    return checks


def summarize_run(r) -> dict:
    """What we keep from a run (enough to re-grade without the API)."""
    p = r.parts
    sections = ("snapshot", "recent_news", "guest_themes", "tech_hints")
    body = r.markdown.split("## Sources", 1)[0]
    return {
        "markdown": r.markdown,
        "brief_body": body,
        "fact_lines": sum(len(p.get(k, [])) for k in sections),
        "uncited_lines": sum(1 for k in sections for line in p.get(k, []) if not line.get("findings")),
        "questions": len(p.get("discovery_questions", [])),
        "use_cases": len(p.get("use_cases", [])),
        "email_words": len(p.get("email", "").split()),
        "findings": [
            {"id": f.id, "topic": f.topic, "claim": f.claim, "sources": [vars(s) for s in f.sources], "flags": f.flags}
            for f in r.findings
        ],  # fmt: skip
        "removed": len(r.critic.get("removed", [])),
        "coverage": r.critic.get("coverage", 0.0),
        "quotes_found": r.critic.get("quotes_found", 0),
        "quotes_checked": r.critic.get("quotes_checked", 0),
        "robots_skipped": r.critic.get("robots_skipped", 0),
        "stale": r.critic.get("stale", 0),
        "dropped_lines": len(r.critic.get("dropped_lines", [])),
        "seconds": round(r.seconds, 1),
        "tokens_in": r.usage.input_tokens,
        "tokens_out": r.usage.output_tokens,
        "searches": r.usage.searches,
        "capped": r.capped,
    }


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def report(split: str, rows: list[dict], runs: int, prices: tuple) -> str:
    p_in, p_out, p_search = prices
    n = len(rows)
    passed = sum(r["pass"] for r in rows)
    checks = {}
    for r in rows:
        for k, v in r["checks"].items():
            checks.setdefault(k, []).append(v)
    sent = sum(len(r["findings"]) + r["removed"] for r in rows)
    kept = sum(len(r["findings"]) for r in rows)
    qf, qc = sum(r["quotes_found"] for r in rows), sum(r["quotes_checked"] for r in rows)
    cost = None
    if p_in is not None:
        cost = (
            sum((r["tokens_in"] * p_in + r["tokens_out"] * p_out) / 1e6 + r["searches"] * p_search / 1000 for r in rows)
            / n
        )
    secs = [r["seconds"] for r in rows]
    per_company = {}
    for r in rows:
        per_company.setdefault(r["company"], []).append(len(r["findings"]))
    lines = [
        f"# Research agent eval: {split} ({date.today().isoformat()})",
        "",
        f"- Model {config.LLM_MODEL}, effort {config.LLM_EFFORT}, {config.WEB_SEARCH_TOOL}, up to "
        f"{config.SEARCHES_PER_QUESTION} searches per question · {len(per_company)} companies × {runs} runs · prices "
        f"${p_in} / ${p_out} per million tokens, ${p_search} per 1,000 searches",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Briefs passing every check | **{passed}/{n}** |",
        f"| Research sentences with a source (the rest removed) | {kept}/{sent} ({kept / sent:.0%}) |"
        if sent
        else "| Research sentences with a source | n/a |",
        f"| Cited quotes found on their page | {qf}/{qc} ({qf / qc:.0%}) |"
        if qc
        else "| Cited quotes found on their page | none checked |",
        f"| Pages not fetched because of robots.txt | {sum(r['robots_skipped'] for r in rows)} |",
        f"| News items older than 12 months (flagged) | {sum(r['stale'] for r in rows)} |",
        f"| Brief lines dropped for citing nothing | {sum(r['dropped_lines'] for r in rows)} |",
        f"| Time per brief | p50 {percentile(secs, 0.5):.0f} s, p95 {percentile(secs, 0.95):.0f} s |",
        f"| Cost per brief | {'not configured' if cost is None else f'${cost:.3f}'} |",
        f"| Web searches per brief | {sum(r['searches'] for r in rows) / n:.1f} |",
        f"| Runs stopped at the cost cap | {sum(r['capped'] for r in rows)} |",
        "",
        "| Check | Pass |",
        "|---|---|",
    ]
    lines += [f"| {k} | {sum(v)}/{len(v)} |" for k, v in sorted(checks.items())]
    lines += ["", "| Company | Sourced findings per run |", "|---|---|"]
    lines += [f"| {c} | {', '.join(map(str, v))} |" for c, v in per_company.items()]
    failing = sorted({f"{r['company']} run {r['run']} ({','.join(k for k, v in r['checks'].items() if not v)})"
                      for r in rows if not r["pass"]})  # fmt: skip
    lines += ["", "Failing: " + ("; ".join(failing) or "none")]
    return "\n".join(lines) + "\n"


def rescore(path: Path, write: bool = False, prices: tuple | None = None) -> int:
    """Re-grade saved briefs with the current checks. Without --write it's the CI gate: any changed verdict fails.
    With --write the runs are saved re-graded, and with prices the report is written again next to them."""
    cases = {c["company"]: c for c in load("all")}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    changed = 0
    for r in rows:
        checks = grade(cases[r["company"]], r)
        ok = all(checks.values())
        changed += ok != r["pass"] or checks.keys() != r["checks"].keys()
        r["pass"], r["checks"] = ok, checks
    print(f"re-scored {len(rows)} briefs, {changed} verdicts changed; pass {sum(r['pass'] for r in rows)}/{len(rows)}")
    if not write:
        return 1 if changed else 0
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    if prices and prices[0] is not None:
        split = "heldout" if "heldout" in path.stem else "dev"
        path.with_suffix(".md").write_text(report(split, rows, max(r["run"] for r in rows), prices), encoding="utf-8")
    return 0


def sample(path: Path, k: int = 30, seed: int = 7) -> Path:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    claims = [(r["company"], r["run"], f) for r in rows for f in r["findings"]]
    random.Random(seed).shuffle(claims)
    out = path.with_name(path.stem + "-labels.csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "company",
                "run",
                "finding",
                "claim",
                "source_url",
                "quote",
                "quote_on_page",
                "supported (yes/no/partly)",
                "note",
            ]
        )
        for company, run, f in claims[:k]:
            s = f["sources"][0] if f["sources"] else {"url": "", "cited_text": "", "verified": ""}
            w.writerow([company, run, f["id"], f["claim"], s["url"], s["cited_text"][:300], s["verified"], "", ""])
    print(f"wrote {out} ({min(k, len(claims))} claims to label)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--split", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--price-in", type=float, default=None)
    ap.add_argument("--price-out", type=float, default=None)
    ap.add_argument("--price-search", type=float, default=None)
    ap.add_argument("--rescore", type=Path)
    ap.add_argument("--write", action="store_true", help="with --rescore: save the re-graded runs and report")
    ap.add_argument("--sample", type=Path)
    args = ap.parse_args(argv)
    if args.rescore:
        return rescore(args.rescore, args.write, (args.price_in, args.price_out, args.price_search))
    if args.sample:
        sample(args.sample)
        return 0
    from research import agents, pipeline

    client, rows = agents.make_client(), []
    REPORTS.mkdir(exist_ok=True)
    stem = REPORTS / f"research-{date.today().isoformat()}-{args.split}"
    saved = Path(f"{stem}.jsonl")
    saved.write_text("", encoding="utf-8")
    for run in range(1, args.runs + 1):
        for case in load(args.split):
            r = pipeline.run(case["company"], case.get("website", ""), client)
            out = summarize_run(r)
            checks = grade(case, out)
            rows.append({"company": case["company"], "fictional": case["fictional"], "run": run,
                         "pass": all(checks.values()), "checks": checks, **out})  # fmt: skip
            with saved.open("a", encoding="utf-8") as fh:  # saved as it goes: a crash keeps the briefs so far
                fh.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
            print(f"run {run} {case['company']}: {'pass' if rows[-1]['pass'] else 'FAIL'} "
                  f"{len(out['findings'])} findings ${r.cost:.3f} {r.seconds:.0f}s", flush=True)  # fmt: skip
    text = report(args.split, rows, args.runs, (args.price_in, args.price_out, args.price_search))
    print(text)
    Path(f"{stem}.md").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
