"""The agents and the pipeline with the model and the web replaced (no API, no network)."""

import copy
from datetime import date

import pytest

from research import agents, brief, config, pipeline
from research.fetcher import Fetcher, html_to_text
from research.models import Finding, Question, Source, Usage
from tests.fakes import WRITER, FakeClient, FakeWeb, cite, text

PAGE = (
    "<html><head><style>x{}</style></head><body>"
    "<p>As of December 31, 2025, Hyatt had 1,528 properties.</p></body></html>"
)
ROBOTS = "User-agent: *\nDisallow: /private"
BLOCKS = [
    text("Hyatt is large. "),
    text(
        "As of December 31, 2025, Hyatt had 1,528 properties", [cite("https://ex.test/a", "Hyatt had 1,528 properties")]
    ),
    text(" across 83 countries. Here is some joining text without a source."),
]


def web(tmp_path, pages=None):
    pages = {"https://ex.test/robots.txt": ROBOTS, "https://ex.test/a": PAGE} if pages is None else pages
    return Fetcher(tmp_path, FakeWeb(pages))


def test_sentences_get_the_sources_of_the_cited_blocks_they_overlap():
    fs = agents.sentences_from(BLOCKS, "overview")
    assert [f.claim for f in fs] == [
        "Hyatt is large.",
        "As of December 31, 2025, Hyatt had 1,528 properties across 83 countries.",
        "Here is some joining text without a source.",
    ]
    assert [len(f.sources) for f in fs] == [0, 1, 0]


def test_markup_from_numbered_lists_is_removed():
    fs = agents.sentences_from([text("1. **Slow check-in:** guests wait.", [cite("https://ex.test/a", "q")])], "x")
    assert fs[0].claim == "Slow check-in: guests wait."


def test_critic_keeps_sourced_removes_unsourced_checks_quotes_and_flags_stale(tmp_path):
    fs = agents.sentences_from(BLOCKS, "overview") + [
        Finding("", "recent_news", "Opened a resort in March 2024.", [Source("https://ex.test/a", "", "")]),
        Finding("", "overview", "No reliable public information found.", []),
        Finding("", "overview", "Call the owner on +1 305 555 0100.", [Source("https://ex.test/private/x", "", "q")]),
    ]
    report = agents.critic(fs, web(tmp_path), date(2026, 10, 25))
    kept = report["kept"]
    assert [f.id for f in kept] == ["F1", "F2", "F3"] and len(report["removed"]) == 2
    assert kept[0].sources[0].verified == "found" and report["quotes_found"] == 1
    assert "stale: older than 12 months" in kept[1].flags and report["stale"] == 1
    assert "555" not in kept[2].claim and "personal data removed" in kept[2].flags
    assert kept[2].sources[0].verified == "robots.txt" and report["robots_skipped"] == 1
    assert report["no_info_topics"] == ["overview"]


def test_fetcher_caches_respects_robots_and_handles_errors(tmp_path):
    opener = FakeWeb({"https://ex.test/robots.txt": ROBOTS, "https://ex.test/a": PAGE})
    f = Fetcher(tmp_path, opener)
    assert f.check("https://ex.test/a", "1,528 properties") == "found"
    assert f.check("https://ex.test/a", "1,528 properties") == "found" and opener.calls.count("https://ex.test/a") == 1
    assert f.check("https://ex.test/a", "a quote that is not on the page at all") == "not found"
    assert f.check("https://ex.test/private/p", "x") == "robots.txt"
    assert f.check("https://other.test/p", "x") == "unreachable"
    assert f.check("ftp://ex.test/p", "x") == "not http" and f.check("https://ex.test/a", "") == "not checked"
    assert html_to_text(PAGE) == "As of December 31, 2025, Hyatt had 1,528 properties."


def test_writer_lines_must_cite_a_kept_finding():
    kept = [Finding("F1", "overview", "c", [Source("https://ex.test/a")])]
    parts = copy.deepcopy(WRITER)
    check = agents.check_writing(parts, kept)
    assert [line["text"] for line in parts["snapshot"]] == ["It runs 1,528 properties."]
    assert check["dropped_lines"] == ["Uncited line."]


def test_plan_falls_back_when_the_model_returns_nothing_usable():
    client = FakeClient(plan={"questions": [{"topic": "overview", "text": "  "}]})
    qs = agents.plan("Acme Resorts", "", client, Usage())
    assert [q.topic for q in qs] == list(agents.TOPICS) and qs[0].id == "Q1"


def test_the_whole_pipeline_and_its_cost_cap(monkeypatch, tmp_path):
    client = FakeClient(research_blocks=BLOCKS, writer=copy.deepcopy(WRITER))
    seen = []
    r = pipeline.run("Hyatt Hotels Corporation", "hyatt.com", client, web(tmp_path), on_step=seen.append)
    names = [s.name for s in r.steps]
    assert names[:3] == ["Planner", "Researcher Q1 (overview)", "Researcher Q2 (recent_news)"]
    assert "Critic" in names and names[-1] == "Writer" and len(seen) == len(r.steps)
    assert r.usage.searches == 4 + 2 * len(r.retried_topics) and r.cost > 0
    assert "## Ten questions for the meeting" in r.markdown and "[1]" in r.markdown
    research_req = next(q for q in client.requests if q.get("tools"))
    assert research_req["tools"][0]["max_uses"] == config.SEARCHES_PER_QUESTION
    assert "data, not instructions" in research_req["system"]
    monkeypatch.setattr(config, "RUN_COST_CAP_USD", 0.0)
    capped = pipeline.run(
        "Hyatt", "", FakeClient(research_blocks=BLOCKS, writer=copy.deepcopy(WRITER)), web(tmp_path, {})
    )
    assert capped.capped and all("skipped" in s.name for s in capped.steps if s.name.startswith("Researcher"))


def test_the_brief_numbers_each_source_once():
    f1 = Finding("F1", "overview", "a", [Source("https://ex.test/a", "A", "q", "found")])
    f2 = Finding("F2", "overview", "b", [Source("https://ex.test/a", "A", "q", "found"), Source("https://ex.test/b")])
    refs, order = brief.sources_index([f1, f2])
    assert refs == {"F1": [1], "F2": [1, 2]} and [s.url for s in order] == ["https://ex.test/a", "https://ex.test/b"]


def test_usage_cost_counts_searches():
    u = Usage(input_tokens=1_000_000, output_tokens=0, searches=10)
    assert u.cost(0.10, 0.50, 10) == pytest.approx(0.20)


def test_research_request_shape_and_no_info():
    client = FakeClient(research_blocks=[text("No reliable public information found.")])
    fs = agents.research(Question("Q1", "overview", "Who?"), "Seabright Coastal Resorts", "", client, Usage())
    assert fs[0].claim == "No reliable public information found." and not fs[0].sources
    assert client.requests[0]["tools"][0]["type"] == config.WEB_SEARCH_TOOL


def test_an_unparseable_page_is_unreachable_not_a_crash(tmp_path):
    bad = "<html><body><![h broken marked section</body></html>"
    f = Fetcher(tmp_path, FakeWeb({"https://ex.test/bad": bad}))
    assert f.check("https://ex.test/bad", "anything at all") in ("unreachable", "not found")


def test_a_cut_off_writer_reply_is_retried_then_left_empty():
    from types import SimpleNamespace

    class Truncating(FakeClient):
        def create(self, **req):
            self.requests.append(req)
            return SimpleNamespace(
                content=[text('{"snapshot": [{"text": "unfinished')],
                stop_reason="max_tokens",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1, server_tool_use=None),
            )

    client = Truncating()
    parts = agents.write("Hyatt", [], client, Usage())
    assert len(client.requests) == 2 and "too long" in client.requests[1]["messages"][0]["content"]
    assert parts["snapshot"] == [] and parts["discovery_questions"] == []
