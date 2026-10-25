"""The eval's grader, report, re-scoring and labelling sample, and a run with the model and the web replaced."""

import copy
import csv
import json

from eval import run_eval as ev
from research import agents, config, pipeline
from research.fetcher import Fetcher
from tests.fakes import WRITER, FakeClient, FakeWeb, cite, text

REAL = {"company": "Hyatt Hotels Corporation", "fictional": False}
FAKE = {"company": "Seabright Coastal Resorts", "fictional": True}


def out(**kw):
    base = {
        "markdown": "# Brief\n- a [1]\n## Sources\n1. x",
        "brief_body": "# Brief\n- a [1]\n",
        "fact_lines": 4,
        "uncited_lines": 0,
        "questions": 10,
        "use_cases": 3,
        "email_words": 60,
    }
    return {**base, **kw}


def test_grade_real_and_fictional_companies():
    assert all(ev.grade(REAL, out()).values())
    bad = ev.grade(REAL, out(questions=9, brief_body="A seamless brief, call 305 555 0100", fact_lines=1))
    assert not bad["structure"] and not bad["no_hype"] and not bad["has_findings"] and not bad["no_personal_data"]
    honest = out(
        fact_lines=0,
        markdown="No reliable public information was found.",
        brief_body="## Snapshot\n- Nothing reliable found.\n",
    )
    assert ev.grade(FAKE, honest)["fictional_honest"]
    assert not ev.grade(FAKE, out())["fictional_honest"]  # facts about a company that doesn't exist
    # The pilot's real phrasing: nothing found, and the near matches named as other businesses, with sources.
    near = (
        "## Snapshot\n- No reliable public information was found about Seabright Coastal Resorts. [1]\n"
        "- The closest matches are different entities: Beachwalk at SeaBright, and neither name matches. [2]\n"
        "## Recent news\n- Nothing reliable found.\n## Ten questions for the meeting\n1. Who runs it?\n"
    )
    assert ev.grade(FAKE, out(brief_body=near, markdown=near, fact_lines=2))["fictional_honest"]
    invented = near.replace("- Nothing reliable found.", "- Seabright opened a new spa in March 2026. [3]")
    assert not ev.grade(FAKE, out(brief_body=invented, markdown=invented, fact_lines=3))["fictional_honest"]
    # Held-out phrasings: honest ("a different kind of business", "separate businesses") vs a pop-up stated as fact.
    honest_ho = near.replace(
        "- Nothing reliable found.",
        "- The one match is a pizza pop-up at a Baltimore hotel, a different kind of business. [3]\n"
        "- Other results were for similarly named but separate businesses. [4]",
    )
    assert ev.grade(FAKE, out(brief_body=honest_ho, markdown=honest_ho, fact_lines=4))["fictional_honest"]
    popup = near.replace("- Nothing reliable found.", "- Harbor & Hearth, a pizza pop-up, is open weekends. [3]")
    assert not ev.grade(FAKE, out(brief_body=popup, markdown=popup, fact_lines=3))["fictional_honest"]
    titled = out(markdown="# Brief\n## Sources\n1. [A seamless travel experience](https://ex.test/seamless)")
    assert ev.grade(REAL, titled)["no_hype"]  # a cited page's title is not the agent's words


def test_email_must_not_describe_the_sender():
    def email(body):
        return out(markdown=f"# Brief\n## Outreach email\n\n> {body}\n\n## Sources\n1. x")

    plain = "Hi, I'd like 30 minutes to learn how your desk works. Thanks, Vamsi"
    assert ev.grade(REAL, email(plain))["email_no_title"]
    for claim in ("I'm a Forward Deployed Engineer looking at", "Hi, I'm Vamsi, an engineer working on AI"):
        assert not ev.grade(REAL, email(claim))["email_no_title"]
    assert ev.grade(REAL, out(markdown="Our engineers said I'm a fan."))["email_no_title"]  # outside the email


def test_run_report_rescore_and_sample(monkeypatch, tmp_path):
    blocks = [text("Hyatt had 1,528 properties.", [cite("https://ex.test/a", "1,528 properties")])]
    client = FakeClient(research_blocks=blocks, writer=copy.deepcopy(WRITER))
    monkeypatch.setattr(agents, "make_client", lambda: client)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    original = pipeline.run
    monkeypatch.setattr(pipeline, "run", lambda c, w, cl: original(c, w, cl, Fetcher(tmp_path / "f", FakeWeb({}))))
    monkeypatch.setattr(ev, "REPORTS", tmp_path)
    assert (
        ev.main(
            ["--split", "heldout", "--runs", "2", "--price-in", "0.1", "--price-out", "0.5", "--price-search", "10"]
        )
        == 0
    )
    md = next(tmp_path.glob("research-*-heldout.md")).read_text(encoding="utf-8")
    assert "| Briefs passing every check |" in md and "Cost per brief | $0." in md
    saved = next(tmp_path.glob("research-*-heldout.jsonl"))
    assert ev.rescore(saved) == 0
    rows = [json.loads(line) for line in saved.read_text(encoding="utf-8").splitlines()]
    rows[0]["pass"] = not rows[0]["pass"]
    saved.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert ev.rescore(saved) == 1
    assert ev.rescore(saved, write=True, prices=(0.1, 0.5, 10)) == 0  # saved re-graded, report written again
    assert ev.rescore(saved) == 0 and saved.with_suffix(".md").exists()
    labels = ev.sample(saved, k=3)
    with labels.open(encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert "supported (yes/no/partly)" in header
