"""Naive one-shot RAG baseline: embed -> search -> take the top hit -> answer.

No grading, no precedence, no validation, no loops. Used only to show why the agent is needed.
"""
from __future__ import annotations

from datetime import timedelta

from laytime_agent import storage
from laytime_agent.tools import documents as D
from laytime_agent.tools import laytime as L
from laytime_agent.tools import terms as T
from laytime_agent.vectorstore import hybrid_search


def run_baseline(case_id: str) -> dict:
    docs = storage.case_documents(case_id)
    sof = D.read_sof(next(d for d in docs if d["doc_type"] == "sof")["path"])
    events, _ = D.classify_events(sof["events"])
    ctx = {"operation": "discharge" if sof["operation"].startswith("disch") else "load"}
    vals = {}
    for t in T.TERMS:                                  # top-1 hit, whatever document it came from
        hits = hybrid_search(T.TERMS[t]["queries"][0].format(op_name=""), case_id, T.SEARCH_TYPES, k=1)
        vals[t] = T.extract_rules(t, hits[0]["text"], ctx) if hits else {}
    nors = sorted((D.read_nor(d["path"]) for d in docs if d["doc_type"] == "nor"), key=lambda n: n["tendered"])
    nor = nors[0]                                       # first NOR, never validated
    trig = vals["nor"].get("trigger") or {"type": "hours_after_nor", "hours": 6}
    nt = D.datetime.strptime(nor["tendered"], D.FMT)
    commence = (nt + timedelta(hours=trig.get("hours", 0))).strftime(D.FMT)
    exclusions = []
    for s in D.pair_stoppages(events):                  # deduct every stoppage, no checks
        if s["end"] and s["end"] > s["start"]:
            exclusions.append({"start": s["start"], "end": s["end"], "reason": s["cause"], "kind": s["cause"],
                               "applies_on_demurrage": True})
    completed = next(e["ts"] for e in events if e["type"] == "COMPLETED")
    rate = vals["laytime_rate"].get("rate_mt_per_day") or 5000
    dem = vals["demurrage"].get("rate_usd_per_day") or 10000
    calc = L.calculate(commence, completed, sof["bl_qty"] / rate * 24, exclusions, dem)
    days = vals["time_bar"].get("days") or 90
    calc["time_bar"] = {"deadline": (D.datetime.strptime(completed, D.FMT) + timedelta(days=days)).date().isoformat()}
    calc["valid_nor"] = nor["number"]
    return calc
