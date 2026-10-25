"""Account research: type a hotel or resort company, get a cited discovery-prep brief, then ask about it.

streamlit run app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import anthropic  # noqa: E402
import streamlit as st  # noqa: E402

from research import agents, chat, config, limits, pipeline, share  # noqa: E402

st.set_page_config(page_title="Account Research Agent", page_icon="🔎", layout="wide")
EXAMPLES = ["Hyatt Hotels Corporation", "Club Med", "Four Seasons Hotels and Resorts"]
FRIENDLY_ERROR = "The research didn't finish: the model or web search didn't answer in time. Please try again later."


def state():
    s = st.session_state
    s.setdefault("briefs", {})  # company -> {"run": Run, "turns": [...]}
    s.setdefault("current", None)
    s.setdefault("asked", 0)
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


def show_steps(steps):
    for i, step in enumerate(steps, 1):
        st.markdown(f"**{i}. {step.name}** · {step.seconds:.1f} s · ${step.cost_usd:.3f}")
        st.json({"input": step.input, "result": step.result}, expanded=False)


def research(company: str, website: str):
    s = state()
    reason = limits.blocked(s.asked)
    if reason:
        st.info(reason, icon=":material/hourglass:")
        return
    s.asked += 1
    with st.status(f"Researching {company}...", expanded=True) as status:
        try:
            run = pipeline.run(
                company, website, on_step=lambda step: status.write(f"✓ {step.name} · {step.seconds:.0f} s")
            )
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.APIStatusError):
            status.update(label="Stopped", state="error")
            st.error(FRIENDLY_ERROR, icon=":material/cloud_off:")
            return
        status.update(
            label=f"Done: {len(run.findings)} sourced findings, ${run.cost:.3f}, {run.seconds:.0f} s", state="complete"
        )
    limits.record(run.cost)
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
    turn = chat.Turn(q)
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        try:
            history = [{"question": t["understood_as"] or t["question"], "answer": t["answer"]} for t in turns]
            st.write_stream(chat.answer(q, history, run.company, run.findings, agents.make_client(), turn))
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.APIStatusError):
            st.error("The model didn't answer in time. Please try again.", icon=":material/cloud_off:")
            return
    cost = (
        turn.usage["input_tokens"] * config.PRICE_IN_PER_M + turn.usage["output_tokens"] * config.PRICE_OUT_PER_M
    ) / 1e6
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
    brief_tab, steps_tab, ask = st.tabs(["Brief", f"Steps ({len(run.steps)})", "Ask about it"])
    with brief_tab:
        st.markdown(run.markdown)
        st.download_button(
            "Download brief.md", run.markdown, file_name=f"brief-{run.company.lower().replace(' ', '-')}.md"
        )
    with steps_tab:
        show_steps(run.steps)
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
with st.form("research"):
    left, right = st.columns([2, 1])
    company = left.text_input("Hotel or resort company", placeholder="e.g. Club Med", max_chars=120)
    website = right.text_input("Website (optional)", placeholder="e.g. clubmed.com", max_chars=200)
    go = st.form_submit_button("Research", type="primary", icon=":material/search:")
st.caption("Try: " + " · ".join(EXAMPLES) + ". About 2 minutes and 10-15 cents a brief.")
if go and company.strip():
    research(company.strip(), website.strip())
s = state()
if s.current and s.current in s.briefs:
    brief_view(s.briefs[s.current])
