"""Shared guardrails, request tracing and the cross-app ops log (hotel-ai-platform), wired for the research agent.

    with ops.start(session_id, "brief") as trace:     one trace per brief or chat question
        v = ops.check_company(name, website)          before any model call or web search
        ...pipeline.run(): planner, each researcher, critic, writer, checks are spans (pipeline._record)...
        ops.finish(trace, run, ...)                   one ops_request_log row + the spans, PII removed first

The ops log is also where this month's spend is read from (`month_spent`), so the monthly cap survives a restart of
Streamlit Cloud, which wipes the local daily counters.
"""

import os
from datetime import UTC, datetime
from functools import lru_cache

from hotelplatform import guardrails, jsonlog, oplog, tracing, version

from research import config

APP = "fde-account-research-agent"
APP_VERSION = "1.1.0"

# A company name or a question about a brief. Names can be in any language and are short, so no language check.
INPUT_POLICY = guardrails.InputPolicy(max_chars=400, languages=())
# Briefs and chat answers cite findings by ID ([F3]); every claim is checked against its page by the critic. Here:
# contact details the findings didn't contain, prompt leaks and off-brand text. No promises to check: it only reads.
OUTPUT_POLICY = guardrails.OutputPolicy(require_citation=False, numbers="off", promises="off", pii_leak="redact")


@lru_cache(maxsize=1)
def store() -> oplog.OpsStore:
    """One per process; nothing connects until the first row (the keep-awake visit never gets that far)."""
    url = os.getenv("DATABASE_URL", "").strip().replace("postgres://", "postgresql://", 1)
    return oplog.OpsStore(APP, url=url, log_dir=config.LOG_DIR / "ops", retention_days=30)


@lru_cache(maxsize=1)
def running_version() -> str:
    return version.version_string(APP_VERSION, config.ROOT)


def configure_logs() -> None:
    jsonlog.configure(APP, running_version())


def start(session_id: str | None):
    return tracing.new_trace(APP, session_id=session_id)


def check_company(company: str, website: str = "") -> guardrails.Verdict:
    return guardrails.check_input(f"{company} {website}".strip(), INPUT_POLICY)


def check_question(text: str) -> guardrails.Verdict:
    return guardrails.check_input(text, INPUT_POLICY)


def check_text(text: str, findings: list, question: str = "") -> guardrails.Verdict:
    sources = [f.claim + " " + " ".join(getattr(s, "cited_text", "") for s in f.sources) for f in findings or []]
    return guardrails.check_output(text, OUTPUT_POLICY, sources=sources, input_text=question)


def month_spent() -> float:
    """This month's spend from the durable ops log; 0.0 when it can't be read (the local files still count)."""
    try:
        start_of_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        rows = store().requests(since=start_of_month.isoformat(timespec="milliseconds"), limit=5000)
        return round(sum(r.get("cost_usd") or 0.0 for r in rows), 6)
    except Exception:  # noqa: BLE001 - the cap then falls back to this disk's files
        return 0.0


def safety_flags(trace) -> list[str]:
    flags = set()
    for span in trace.spans if trace is not None else []:
        if span.name.startswith("guardrails."):
            stage = span.name.split(".", 1)[1]
            flags.update(span.attributes.get("flags") or [])
            flags.update(f"{stage}:{r}" for r in span.attributes.get("reasons") or [])
    return sorted(flags)


def finish(trace, request_type: str, status: str, cost: float = 0.0, seconds: float = 0.0, tokens=(0, 0),
           error_type: str | None = None, sources=(), data: dict | None = None) -> bool:  # fmt: skip
    """Write the ops row for one brief or chat question. Never raises, never blocks."""
    if trace is None:
        return False
    try:
        row = oplog.request_row(
            trace,
            request_type=request_type,
            status=status,
            latency_ms=round(seconds * 1000, 1) or trace.elapsed_ms(),
            error_type=error_type,
            tokens_in=tokens[0],
            tokens_out=tokens[1],
            cost_usd=cost,
            model=config.LLM_MODEL if cost else None,
            sources=list(sources)[:50],
            safety_flags=safety_flags(trace),
            version=running_version(),
            data=data or {},
        )
        if status == "capped":
            jsonlog.cap_hit(error_type or "cap", trace_id=trace.trace_id)
        return store().submit(trace, row)
    except Exception:
        return False


def dependencies() -> dict[str, str]:
    return {
        "anthropic": "configured" if os.getenv("ANTHROPIC_API_KEY") else "missing key",
        "web search": "Anthropic web search tool (paid per search)",
        "demo code": "set" if config.demo_code() else "missing (live runs limited to the public daily cap)",
        "ops log": store().health()["status"],
        "model": config.LLM_MODEL,
    }


def caps() -> dict[str, float]:
    return {"cost_cap_day": config.DAILY_COST_CAP_USD, "cost_cap_month": config.MONTHLY_COST_CAP_USD}
