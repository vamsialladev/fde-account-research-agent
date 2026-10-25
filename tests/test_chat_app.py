"""Chat about a brief, share links, limits, and the app via Streamlit AppTest (model and web replaced)."""

import copy
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from research import agents, chat, config, limits, pipeline, share
from research.fetcher import Fetcher
from research.models import Finding, Source
from tests.fakes import WRITER, FakeClient, FakeWeb, cite, text

ROOT = config.ROOT
FINDINGS = [
    Finding("F1", "overview", "Hyatt had 1,528 properties at the end of 2025.", [Source("https://ex.test/a")]),
    Finding("F2", "guest_feedback", "Slow check-in is a recurring complaint.", [Source("https://ex.test/b")]),
]


def test_chat_answers_from_findings_and_rewrites_follow_ups():
    client = FakeClient(answer="Slow check-in [F2], see also [F9].", rewrite="What do guests complain about at Hyatt?")
    turn = chat.Turn("and what about complaints?")
    out = "".join(chat.answer("and what about complaints?", [{"question": "Size?", "answer": "1,528"}], "Hyatt",
                              FINDINGS, client, turn))  # fmt: skip
    assert out == turn.answer and turn.cited == ["F2"] and turn.understood_as.startswith("What do guests")
    assert "[F2] Slow check-in" in client.requests[-1]["messages"][0]["content"]
    assert turn.usage["calls"] == 2
    plain = chat.Turn("How many properties?")
    list(chat.answer("How many properties?", [], "Hyatt", FINDINGS, FakeClient(), plain))
    assert plain.usage["calls"] == 1 and plain.understood_as == ""


def test_share_round_trip_redacts_and_rejects_damage():
    token = share.make_token("Hyatt", "# Brief\nok", [{"question": "Email me at a@b.test", "answer": "Sure."}])
    data = share.decode(token)
    assert data["brief"] == "# Brief\nok" and "a@b.test" not in data["turns"][0]["q"]
    assert share.decode("nope") is None and share.decode("") is None
    assert share.make_token("x", "y" * 200_000, []) is None or len(share.make_token("x", "y" * 200_000, [])) <= 12_000
    assert share.share_url("https://app.test/?a=1", "t") == "https://app.test/?share=t"


def test_limits(tmp_path, monkeypatch):
    assert limits.blocked(0, log_dir=tmp_path) is None
    assert "per visit" in limits.blocked(config.MAX_BRIEFS_PER_SESSION, log_dir=tmp_path)
    monkeypatch.setattr(config, "DAILY_COST_CAP_USD", 0.1)
    day = date(2026, 10, 25)
    limits.record(0.06, day=day, log_dir=tmp_path)
    assert limits.record(0.05, count=False, day=day, log_dir=tmp_path) == {"questions": 1, "cost_usd": 0.11}
    assert "today's limit" in limits.blocked(0, day=day, log_dir=tmp_path)


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    blocks = [text("Hyatt had 1,528 properties.", [cite("https://ex.test/a", "1,528 properties")])]
    client = FakeClient(research_blocks=blocks, writer=copy.deepcopy(WRITER))
    monkeypatch.setattr(agents, "make_client", lambda: client)
    original = pipeline.run
    monkeypatch.setattr(pipeline, "run", lambda c, w="", on_step=None: original(
        c, w, client, Fetcher(tmp_path / "f", FakeWeb({})), on_step))  # fmt: skip
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)


def test_research_shows_brief_steps_and_chat(app):
    app.run()
    assert not app.exception
    app.text_input[0].input("Hyatt Hotels Corporation")
    app.button[0].click().run()
    assert not app.exception
    assert any("Discovery-prep brief: Hyatt Hotels Corporation" in m.value for m in app.markdown)
    assert [t.label for t in app.tabs][:2] == ["Brief", "Steps (6)"]
    app.chat_input[0].set_value("How many properties?").run()
    assert any("1,528 properties [F1]" in m.value for m in app.markdown)
    next(b for b in app.button if b.label == "Share this brief").click().run()
    url = next(c.value for c in app.code if "?share=" in c.value)
    shared = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    shared.query_params["share"] = url.split("?share=", 1)[1]
    shared.run()
    assert "Shared discovery-prep brief" in shared.title[0].value and not shared.chat_input


def test_session_limit_stops_before_research(app, monkeypatch):
    monkeypatch.setattr(config, "MAX_BRIEFS_PER_SESSION", 0)
    app.run()
    app.text_input[0].input("Hyatt")
    app.button[0].click().run()
    assert any("per visit" in i.value for i in app.info)


def test_damaged_share_link(app):
    app.query_params["share"] = "x"
    app.run()
    assert any("damaged" in w.value for w in app.warning)
