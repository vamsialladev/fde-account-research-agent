"""scripts/business_case.py: the arithmetic and the scenario table (pure; no model)."""

import importlib.util
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("business_case", ROOT / "scripts" / "business_case.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)


def test_base_case_arithmetic():
    r = bc.per_year(bc.Assumptions(), team=8)
    assert r["first meetings"] == 384  # 4 a month x 12 x 8
    assert round(r["hours saved"]) == 288  # 384 x (2.5 h x 40% - 15 min)
    assert round(r["net value"]) == round(r["time saved ($)"] - r["AI cost"] - r["hosting"])


def test_scenarios_are_ordered_and_review_time_can_cancel_the_saving():
    base = bc.Assumptions()
    nets = [bc.per_year(replace(base, **bc.SCENARIOS[n]), 8)["net value"] for n in bc.SCENARIOS]
    assert nets == sorted(nets)
    slow_review = bc.per_year(replace(base, review_minutes=60), 8)
    assert slow_review["hours saved"] == 0 and slow_review["net value"] < 0


def test_cli_prints_a_table(capsys):
    assert bc.main(["--scenarios", "--cost-per-brief", "0.2"]) == 0
    out = capsys.readouterr().out
    assert "| net value |" in out and "pessimistic" in out and "assumptions, not measurements" in out
