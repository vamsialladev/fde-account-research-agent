"""The example briefs are copied from a saved eval run, unchanged (scripts/make_examples.py)."""

import json

from research import examples
from scripts import make_examples


def test_examples_match_their_source_records():
    records = make_examples.records()
    saved = examples.load()
    assert list(saved) == list(make_examples.COMPANIES)
    for company, example in saved.items():
        source = records[company]
        for field in make_examples.FIELDS:
            assert example[field] == source[field], (company, field)
        assert example["source"].endswith("(run 1)")


def test_example_becomes_a_run_the_page_can_show():
    run = examples.to_run(examples.load()["Club Med"])
    assert len(run.findings) == 41 and run.findings[0].id == "F1" and run.findings[0].sources[0].url
    assert run.critic == {"quotes_found": 32, "quotes_checked": 37}
    assert 0.1 < run.cost < 0.2
    json.dumps(run.markdown)
