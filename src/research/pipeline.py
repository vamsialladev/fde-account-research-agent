"""planner -> researchers -> critic -> (one more pass for thin topics) -> writer -> checks -> brief.

Every step is recorded with its input, structured result, time and cost. The run stops starting new research when
its cost reaches RUN_COST_CAP_USD minus what the writer needs, so a brief never costs more than the cap.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from research import agents, brief, config
from research.fetcher import Fetcher
from research.models import Finding, Step, Usage

WRITER_RESERVE_USD = 0.02  # kept back so the brief can still be written at the cap


@dataclass
class Run:
    company: str
    website: str = ""
    steps: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    findings: list = field(default_factory=list)  # kept, with ids
    critic: dict = field(default_factory=dict)
    parts: dict = field(default_factory=dict)
    markdown: str = ""
    usage: Usage = field(default_factory=Usage)
    seconds: float = 0.0
    capped: bool = False
    retried_topics: list = field(default_factory=list)

    @property
    def cost(self) -> float:
        return self.usage.cost(config.PRICE_IN_PER_M, config.PRICE_OUT_PER_M, config.PRICE_PER_1K_SEARCHES)


def _record(run: Run, name: str, inp: dict, out: dict, start: float, cost_before: float, on_step) -> None:
    step = Step(name, inp, out, round(time.perf_counter() - start, 2), round(run.cost - cost_before, 4))
    run.steps.append(step)
    if on_step:
        on_step(step)


def run(
    company: str, website: str = "", client=None, fetcher: Fetcher | None = None, on_step: Callable | None = None
) -> Run:
    company = " ".join(company.split())[:120]
    website = website.strip()[:200]
    r = Run(company, website)
    client = client or agents.make_client()
    fetcher = fetcher if fetcher is not None else Fetcher()
    start = time.perf_counter()

    t, c0 = time.perf_counter(), r.cost
    r.questions = agents.plan(company, website, client, r.usage)
    _record(
        r,
        "Planner",
        {"company": company, "website": website},
        {"questions": [f"{q.topic}: {q.text}" for q in r.questions]},
        t,
        c0,
        on_step,
    )

    raw: list[Finding] = []
    for q in r.questions:
        if r.cost >= config.RUN_COST_CAP_USD - WRITER_RESERVE_USD:
            r.capped = True
            _record(
                r,
                f"Researcher {q.id} skipped",
                {"question": q.text},
                {"why": "run cost cap reached"},
                time.perf_counter(),
                r.cost,
                on_step,
            )
            continue
        t, c0 = time.perf_counter(), r.cost
        found = agents.research(q, company, website, client, r.usage)
        raw += found
        _record(r, f"Researcher {q.id} ({q.topic})", {"question": q.text},
                {"findings": len(found), "sources": sum(len(f.sources) for f in found)}, t, c0, on_step)  # fmt: skip

    t, c0 = time.perf_counter(), r.cost
    report = agents.critic(raw, fetcher)
    _record(r, "Critic", {"findings": len(raw)}, _critic_summary(report), t, c0, on_step)

    thin = report["thin_topics"]
    if thin and not r.capped and r.cost < config.RUN_COST_CAP_USD - WRITER_RESERVE_USD * 2:
        t, c0 = time.perf_counter(), r.cost
        retry = [q for q in r.questions if q.topic in thin][:2]
        for q in retry:
            if r.cost >= config.RUN_COST_CAP_USD - WRITER_RESERVE_USD:
                r.capped = True
                break
            raw += agents.research(q, company, website, client, r.usage, hint="The first search found nothing usable: "
                                   "try the company's own site, investor or press pages, or new wording.")  # fmt: skip
            r.retried_topics.append(q.topic)
        report = agents.critic(raw, fetcher)
        _record(r, "Critic sent work back once", {"topics": r.retried_topics}, _critic_summary(report), t, c0, on_step)

    r.findings, r.critic = report["kept"], report
    t, c0 = time.perf_counter(), r.cost
    r.parts = agents.write(company, r.findings, client, r.usage)
    check = agents.check_writing(r.parts, r.findings)
    _record(r, "Writer", {"findings": len(r.findings)},
            {"lines": sum(len(r.parts[k]) for k in ("snapshot", "recent_news", "guest_themes", "tech_hints")),
             "questions": len(r.parts.get("discovery_questions", [])),
             "dropped_uncited_lines": len(check["dropped_lines"])},
            t, c0, on_step)  # fmt: skip
    r.critic["dropped_lines"] = check["dropped_lines"]
    r.seconds = time.perf_counter() - start
    r.markdown = brief.render(r)
    return r


def _critic_summary(report: dict) -> dict:
    return {
        "kept": len(report["kept"]),
        "removed_no_source": len(report["removed"]),
        "coverage": round(report["coverage"], 3),
        "quotes_found_on_page": f"{report['quotes_found']}/{report['quotes_checked']}",
        "robots_skipped": report["robots_skipped"],
        "stale_news": report["stale"],
        "no_public_info": report["no_info_topics"],
        "thin_topics": report["thin_topics"],
    }
