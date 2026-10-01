"""Exercises every LLM code path (planning, grading, re-query, vision re-reads, letter, lessons)
with a stand-in model, so no API key is needed. Real-model behaviour is checked with `python run.py eval`."""
import json
import os
import re

import pytest

os.environ.setdefault("AS_OF_DATE", "2026-10-01")


class StandInLLM:
    provider, model, calls = "stand-in", "test", 0
    available = True
    label = "stand-in:test"

    def json(self, system, prompt, images=None, max_tokens=1500):
        from laytime_agent.llm import _extract_json
        return _extract_json(self._call(system, prompt, images))

    def text(self, system, prompt, images=None, max_tokens=1500):
        return self._call(system, prompt, images)

    def _call(self, system, prompt, images=None):
        from laytime_agent.tools import terms as T
        self.calls += 1
        if images:
            if "NOR No. 1" in prompt:
                return json.dumps({"answer": "NOR No. 1 marker at 16°05.2'N 060°51.3'E, status Drifting",
                                   "quote": "16°05.2'N 060°51.3'E"})
            if "what date is written" in prompt:
                return json.dumps({"answer": "15/06/2026 - '14' struck through, '15' handwritten", "quote": "15"})
            if "weather codes" in prompt:
                return json.dumps({"answer": "Weather code bc, visibility 10 nm, no rain. 10:30 stopped by receivers' order",
                                   "quote": "No rain / no precipitation"})
            return json.dumps({"image_type": "other", "summary": "stand-in vision summary"})
        if "Improve the checklist" in prompt:
            return json.dumps({"steps": ["Read SOF and NORs", "Resolve terms", "Validate", "Calculate"]})
        if "Term needed" in prompt:
            m = re.search(r"Source document type: (\w+) \((.*?) - (.*?)\)\.\nText:\n\"\"\"(.*)\"\"\"", prompt, re.S)
            dtype, _ref, title, text = m.groups()
            op = re.search(r"Operation at this port: (\w+)", prompt).group(1)
            term = next(k for k, v in T.TERMS.items() if v["label"] in prompt)
            ok, why = T.grade_rules(term, {"title": title, "text": text, "doc_type": dtype}, {"operation": op})
            return json.dumps({"relevant": ok, "reason": why,
                               "value": T.extract_rules(term, text, {"operation": op}) if ok else {}})
        if "Polish the letter" in system:
            return prompt
        if "one short lesson" in system:
            return "Santa Rilla: verify NOR position against port limits before accepting NOR time."
        return "{}"


@pytest.fixture(scope="module")
def stand_in():
    from laytime_agent import ingest, llm
    old = llm._LLM
    llm._LLM = StandInLLM()
    ingest.ingest(reset=True)
    yield llm._LLM
    llm._LLM = old


def test_case_c_with_llm_paths(stand_in):
    from laytime_agent import service
    r = service.start_run("case_C_seren_talon", auto_approve=True)
    st = service.get_state(r["run_id"])
    assert r["status"] == "completed"
    assert abs(st["calc"]["amount_usd"] - 32290.10) <= 1
    nor = next(x for x in st["reread_results"] if x["request"]["type"] == "nor_position")
    ais = next(s for s in nor["sources"] if s["source"].startswith("AIS"))
    assert ais["within"] is False and 13.5 < ais["distance_nm"] < 14.5          # vision + geo check agree
    corr = st["corrections"][0]
    assert "signed SOF scan" in corr["evidence"]
    assert stand_in.calls > 20
