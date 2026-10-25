"""The brief as Markdown: every line cites numbered sources, then the questions, use cases, email, sources and the
critic's report (what was removed, flagged and checked)."""

from research import config

CHECK = {"yes": "Yes", "probably": "Probably", "unknown": "Unknown", "no": "No"}


def sources_index(findings: list) -> tuple[dict, list]:
    """Finding id -> source numbers, and the numbered source list (each URL once)."""
    order, by_url, refs = [], {}, {}
    for f in findings:
        nums = []
        for s in f.sources:
            if s.url not in by_url:
                by_url[s.url] = len(order) + 1
                order.append(s)
            nums.append(by_url[s.url])
        refs[f.id] = sorted(set(nums))
    return refs, order


def _cite(ids: list, refs: dict) -> str:
    nums = sorted({n for i in ids for n in refs.get(i, [])})
    return " " + "".join(f"[{n}]" for n in nums) if nums else ""


def render(run) -> str:
    refs, sources = sources_index(run.findings)
    p, c = run.parts, run.critic
    out = [
        f"# Discovery-prep brief: {run.company}",
        "",
        f"Prepared {config.today().isoformat()} for a first meeting. Every line cites its sources; lines the "
        "critic couldn't source were removed. Research by an AI agent from public web pages: check before quoting.",
        "",
    ]
    for title, key in (("Snapshot", "snapshot"), ("Recent news (last 12 months)", "recent_news"),
                       ("What guests say (themes)", "guest_themes"), ("Technology hints", "tech_hints")):  # fmt: skip
        out.append(f"## {title}")
        out.append("")
        lines = p.get(key, [])
        out += [f"- {line['text']}{_cite(line['findings'], refs)}" for line in lines] or ["- Nothing reliable found."]
        out.append("")
    out += ["## Ten questions for the meeting", ""]
    out += [f"{i}. {q}" for i, q in enumerate(p.get("discovery_questions", [])[:10], 1)]
    out += ["", "## Three use-case hypotheses (4-check test)", ""]
    out += [
        "| Use case | Why | Felt | Would pay | Buildable in a week | First user known |",
        "|---|---|---|---|---|---|",
    ]
    for uc in p.get("use_cases", [])[:3]:
        out.append(
            f"| {uc['name']} | {uc['why']}{_cite(uc['findings'], refs)} | {CHECK[uc['felt']]} | "
            f"{CHECK[uc['would_pay']]} | {CHECK[uc['buildable_in_a_week']]} | {CHECK[uc['first_user_known']]} |"
        )
    out += ["", "## Outreach email", "", *[f"> {line}" if line else ">" for line in p.get("email", "").splitlines()]]
    out += ["", "## Sources", ""]
    for i, s in enumerate(sources, 1):
        out.append(f"{i}. [{s.title or s.url}]({s.url}) · quote on page: {s.verified}")
    if not sources:
        out.append("None: no reliable public information was found.")
    out += [
        "",
        "## How this brief was checked",
        "",
        f"- Findings kept: {len(run.findings)}; removed for having no source: {len(c.get('removed', []))}; brief lines "
        f"dropped for citing nothing: {len(c.get('dropped_lines', []))}.",
        f"- Cited quotes found on their page: {c.get('quotes_found', 0)} of {c.get('quotes_checked', 0)} checked; "
        f"not fetched because robots.txt disallows it: {c.get('robots_skipped', 0)}.",
        f"- News older than 12 months flagged: {c.get('stale', 0)}. Topics with no reliable public information: "
        f"{', '.join(c.get('no_info_topics', [])) or 'none'}.",
        f"- Cost {run.cost:.3f} USD ({run.usage.searches} web searches, {run.usage.calls} model calls), "
        f"{run.seconds:.0f} s{' · stopped early at the cost cap' if run.capped else ''}.",
    ]
    return "\n".join(out) + "\n"
