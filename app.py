"""Account research: type a hotel or resort company, get a cited discovery-prep brief, then ask about it.

streamlit run app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import uuid  # noqa: E402

import anthropic  # noqa: E402
import streamlit as st  # noqa: E402
from hotelplatform import admin_gate, bots, jsonlog  # noqa: E402

from research import agents, chat, config, examples, limits, ops, pipeline, share  # noqa: E402

st.set_page_config(page_title="Account Research Agent", page_icon="🔎", layout="wide")
FRIENDLY_ERROR = "The research didn't finish: the model or web search didn't answer in time. Please try again later."


def state():
    s = st.session_state
    s.setdefault("briefs", {})  # company -> {"run": Run, "turns": [...]}
    s.setdefault("current", None)
    s.setdefault("asked", 0)
    s.setdefault("session_id", uuid.uuid4().hex[:12])  # anonymous: groups one visit's traces
    return s


def sidebar():
    s = state()
    with st.sidebar:
        st.caption(
            f"Each brief: about {config.MAX_QUESTIONS} research questions, up to {config.SEARCHES_PER_QUESTION} web "
            f"searches each, stopped at ${config.RUN_COST_CAP_USD:.2f}. "
            f"{config.MAX_BRIEFS_PER_SESSION} briefs per visit."
        )
        if s.briefs:
            st.caption("Briefs in this tab")
        for name in reversed(list(s.briefs)):
            if st.button(("▸ " if name == s.current else "") + name, key=f"b-{name}", use_container_width=True):
                s.current = name
                s.pop("share", None)
                st.rerun()
        st.divider()
        if config.DEMO_VIDEO_URL:
            st.link_button("Watch the 90-second demo", config.DEMO_VIDEO_URL, icon=":material/play_circle:")
        st.link_button("GitHub", config.REPO_URL, icon=":material/code:")
        st.link_button("Portfolio", config.PORTFOLIO_URL, icon=":material/person:")
        st.caption(
            "Pre-sales tooling for a simulated client engagement. It reads public web pages, respects robots.txt, "
            "and never collects personal data about private individuals."
        )
        st.caption(
            "Privacy: questions, briefs and each step's trace are logged to improve the service, with personal "
            "details removed first, and deleted after 30 days."
        )


def show_steps(steps):
    for i, step in enumerate(steps, 1):
        st.markdown(f"**{i}. {step.name}** · {step.seconds:.1f} s · ${step.cost_usd:.3f}")
        st.json({"input": step.input, "result": step.result}, expanded=False)


def research(company: str, website: str, code: str = ""):
    """One live brief = one trace (hotel-ai-platform): the input check, then every pipeline step as a span."""
    s = state()
    with ops.start(s.session_id) as trace:
        _research(company, website, code, trace)


def _research(company: str, website: str, code: str, trace):
    s = state()
    code_ok = limits.has_code(code)
    reason = limits.blocked(s.asked, code_ok=code_ok, month_spent=limits.month_cost(durable=ops.month_spent()))
    if reason:
        st.info(reason, icon=":material/hourglass:")
        ops.finish(trace, "brief", "capped", error_type="limit")
        return
    verdict = ops.check_company(company, website)  # before any model call or paid web search
    if not verdict.allowed:
        st.warning(verdict.message, icon=":material/block:")
        ops.finish(trace, "brief", "blocked", error_type=verdict.reason)
        return
    s.asked += 1
    with st.status(f"Researching {company}...", expanded=True) as status:
        try:
            run = pipeline.run(
                company, website, on_step=lambda step: status.write(f"✓ {step.name} · {step.seconds:.0f} s")
            )
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.APIStatusError) as exc:
            status.update(label="Stopped", state="error")
            st.error(f"{FRIENDLY_ERROR} Reference: {trace.reference}", icon=":material/cloud_off:")
            jsonlog.exception(exc, trace_id=trace.trace_id, where="research")
            ops.finish(trace, "brief", "timeout" if isinstance(exc, anthropic.APITimeoutError) else "error",
                       error_type=type(exc).__name__)  # fmt: skip
            return
        status.update(
            label=f"Done: {len(run.findings)} sourced findings, ${run.cost:.3f}, {run.seconds:.0f} s", state="complete"
        )
    checked = ops.check_text(run.markdown, run.findings)
    run.markdown = checked.text if checked.allowed else run.markdown  # contact details the findings didn't contain
    limits.record(run.cost, public=not code_ok)
    ops.finish(trace, "brief", "ok" if checked.allowed else "blocked", cost=run.cost, seconds=run.seconds,
               tokens=(run.usage.input_tokens, run.usage.output_tokens),
               error_type=None if checked.allowed else checked.reason,
               sources=[s.url for f in run.findings for s in f.sources][:50],
               data={"company": run.company, "findings": len(run.findings), "live": True,
                     "with_code": code_ok})  # fmt: skip
    s.briefs[run.company] = {"run": run, "turns": []}
    s.current = run.company
    s.pop("share", None)
    st.rerun()


def ask_tab(entry):
    run, turns = entry["run"], entry["turns"]
    for t in turns:
        with st.chat_message("user"):
            st.markdown(t["question"])
            if t.get("understood_as"):
                st.caption(f"Understood as: {t['understood_as']}")
        with st.chat_message("assistant"):
            st.markdown(t["answer"])
            if t["cited"]:
                st.caption("From findings " + ", ".join(t["cited"]))
    q = st.chat_input("Ask about this brief (no new web searches)")
    if not q:
        return
    with ops.start(state().session_id) as trace:
        _chat_turn(q, run, turns, trace)


def _chat_turn(q: str, run, turns, trace):
    if limits.month_cost(durable=ops.month_spent()) >= config.MONTHLY_COST_CAP_USD:
        st.info("The demo has reached this month's spending limit.", icon=":material/hourglass:")
        ops.finish(trace, "chat", "capped", error_type="monthly_cap")
        return
    verdict = ops.check_question(q)
    if not verdict.allowed:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            st.markdown(verdict.message)
        ops.finish(trace, "chat", "blocked", error_type=verdict.reason)
        return
    turn = chat.Turn(q)
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        try:
            history = [{"question": t["understood_as"] or t["question"], "answer": t["answer"]} for t in turns]
            with trace.span("chat_answer", findings=len(run.findings)) as span:
                st.write_stream(chat.answer(verdict.text, history, run.company, run.findings, agents.make_client(),
                                            turn))  # fmt: skip
                span.set(tokens_in=turn.usage["input_tokens"], tokens_out=turn.usage["output_tokens"])
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.APIStatusError) as exc:
            st.error(f"The model didn't answer in time. Please try again. Reference: {trace.reference}",
                     icon=":material/cloud_off:")  # fmt: skip
            jsonlog.exception(exc, trace_id=trace.trace_id, where="chat")
            ops.finish(trace, "chat", "error", error_type=type(exc).__name__)
            return
    cost = (
        turn.usage["input_tokens"] * config.PRICE_IN_PER_M + turn.usage["output_tokens"] * config.PRICE_OUT_PER_M
    ) / 1e6
    checked = ops.check_text(turn.answer, run.findings, verdict.text)
    turn.answer = checked.text
    ops.finish(trace, "chat", "ok" if checked.allowed else "blocked", cost=cost,
               tokens=(turn.usage["input_tokens"], turn.usage["output_tokens"]),
               error_type=None if checked.allowed else checked.reason, sources=turn.cited,
               data={"company": run.company, "question": q, "answer": turn.answer})  # fmt: skip
    limits.record(cost, count=False)
    turns.append({"question": q, "understood_as": turn.understood_as, "answer": turn.answer, "cited": turn.cited})
    state().pop("share", None)
    st.rerun()


def brief_view(entry):
    run = entry["run"]
    c = run.critic
    cols = st.columns(4)
    cols[0].metric("Sourced findings", len(run.findings))
    cols[1].metric("Quotes found on their page", f"{c.get('quotes_found', 0)}/{c.get('quotes_checked', 0)}")
    cols[2].metric("Cost", f"${run.cost:.3f}")
    cols[3].metric("Time", f"{run.seconds:.0f} s")
    if not run.steps:  # saved examples: the eval runs they come from never recorded steps (examples.to_run)
        st.caption("Saved example: its steps weren't recorded. Run a live brief to see them.")
        brief_tab, ask = st.tabs(["Brief", "Ask about it"])
    else:
        brief_tab, steps_tab, ask = st.tabs(["Brief", f"Steps ({len(run.steps)})", "Ask about it"])
        with steps_tab:
            show_steps(run.steps)
    with brief_tab:
        st.markdown(run.markdown)
        st.download_button(
            "Download brief.md", run.markdown, file_name=f"brief-{run.company.lower().replace(' ', '-')}.md"
        )
    with ask:
        ask_tab(entry)
    if st.button("Share this brief", icon=":material/link:"):
        state().share = share.make_token(run.company, run.markdown, entry["turns"])
    token = state().get("share")
    if token:
        st.caption("Read-only link (the brief is inside the link; nothing is stored):")
        st.code(share.share_url(st.context.url, token), language=None, wrap_lines=True)


def shared_view(token: str):
    data = share.decode(token)
    st.title("🔎 Shared discovery-prep brief")
    st.caption("Read-only. Personal data was removed before the link was made.")
    if not data:
        st.warning("This link is damaged or from a different version of the app.", icon=":material/link_off:")
        return
    st.markdown(data["brief"])
    for t in data["turns"]:
        with st.chat_message("user"):
            st.text(t["q"])
        with st.chat_message("assistant"):
            st.text(t.get("a", ""))
    st.link_button("Research a company yourself", "?", icon=":material/search:")


def examples_row():
    """Three saved briefs anyone can open: no live run, no cost."""
    saved = examples.load()
    if not saved:
        return
    st.markdown(f"**Example briefs** (saved from the {examples.SAVED_ON} eval run, not refreshed; free to open)")
    for col, company in zip(st.columns(len(saved)), saved, strict=True):
        if col.button(company, key=f"ex-{company}", icon=":material/description:", use_container_width=True):
            s = state()
            s.briefs[f"{company} (example)"] = {"run": examples.to_run(saved[company]), "turns": []}
            s.current = f"{company} (example)"
            s.pop("share", None)
            st.rerun()


def main_page():
    token = st.query_params.get("share")
    if token:
        shared_view(token)
        st.stop()
    st.title("🔎 Account Research Agent")
    st.caption(
        "Pre-sales for the simulated hotel engagement: a cited brief to bring to a first client meeting · planner → "
        "researchers → critic → writer · public web pages only"
    )
    sidebar()
    examples_row()
    with st.form("research"):
        left, right = st.columns([2, 1])
        company = left.text_input("Hotel or resort company", placeholder="e.g. Club Med", max_chars=120)
        website = right.text_input("Website (optional)", placeholder="e.g. clubmed.com", max_chars=200)
        code = st.text_input(
            "Demo code (optional)",
            type="password",
            help=f"Without a code, live briefs are limited to {config.PUBLIC_DAILY_BRIEF_CAP} a day across everyone.",
        )
        go = st.form_submit_button("Research live", type="primary", icon=":material/search:")
    st.caption("A live brief takes about 2 minutes and costs 10-15 cents in model calls and web searches.")
    if go and company.strip():
        research(company.strip(), website.strip(), code)
    s = state()
    if s.current and s.current in s.briefs:
        brief_view(s.briefs[s.current])


@st.cache_resource(show_spinner=False)
def startup_log() -> bool:
    """Once per server start: the JSON lines every hotel app writes (version, settings set/missing, dependencies)."""
    ops.configure_logs()
    jsonlog.app_start(app_version=ops.APP_VERSION)
    jsonlog.config_loaded(["ANTHROPIC_API_KEY", "DEMO_CODE", "ADMIN_PASSWORD", "DATABASE_URL"], model=config.LLM_MODEL)
    jsonlog.dependency_health(ops.dependencies())
    return True


if bots.is_bot(st.query_params):  # streamlit-keep-awake: the page loads; no model call, no web search, no log row
    st.caption("Awake.")
    st.stop()
startup_log()
pages = [st.Page(main_page, title="Research", icon=":material/search:", default=True)]
if admin_gate.enabled():  # no Admin page at all without ADMIN_PASSWORD; out of the menu until signed in
    gate = st.session_state.get("_gate_admin")
    pages.append(st.Page("views/admin.py", title="Admin", icon=":material/admin_panel_settings:", url_path="admin",
                         visibility="visible" if gate and gate.unlocked else "hidden"))  # fmt: skip
st.navigation(pages, position="hidden" if len(pages) == 1 else "sidebar").run()
