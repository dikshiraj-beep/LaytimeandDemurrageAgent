"""End-to-end: ingest the sample pack and run the full agent graph on all three cases.

Runs in whatever LLM mode .env selects; in mock mode it needs no API key or network.
"""
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("AS_OF_DATE", "2026-10-01")
ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "evals" / "answer_key.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def ingested():
    from laytime_agent import ingest
    ingest.ingest(reset=True)


@pytest.mark.parametrize("cid", ["A", "B", "C"])
def test_case_matches_answer_key(cid):
    from laytime_agent import service, storage
    exp = KEY[cid]
    case_id = storage.one("SELECT case_id FROM cases WHERE vessel=?", (exp["vessel"],))["case_id"]
    r = service.start_run(case_id, auto_approve=True)
    assert r["status"] == "completed"
    calc = service.get_state(r["run_id"])["calc"]
    assert calc["result"] == exp["result"]
    assert abs(calc["amount_usd"] - exp["amount_usd"]) <= 1
    assert calc["laytime_commenced"] == exp["laytime_commenced"]
    assert calc["time_bar"]["deadline"] == exp["claim_time_bar"]


def test_human_checkpoint_pause_and_resume():
    from laytime_agent import service, storage
    case_id = storage.one("SELECT case_id FROM cases WHERE vessel=?", (KEY["A"]["vessel"],))["case_id"]
    r = service.start_run(case_id, auto_approve=False)
    assert r["status"] == "awaiting_approval"
    assert not service.get_state(r["run_id"]).get("letter")
    r2 = service.decide(r["run_id"], approved=True, approver="pytest")
    assert r2["status"] == "completed"
    assert "USD 27,825.00" in service.get_state(r["run_id"])["letter"]
