"""Service layer used by both the Streamlit UI and the FastAPI REST API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable

from langgraph.types import Command

from . import storage
from .agent.graph import get_graph
from .llm import get_llm


def _cfg(run_id):
    return {"configurable": {"thread_id": run_id}, "recursion_limit": 60}


def _stream(run_id, payload, on_event: Callable | None):
    graph = get_graph()
    seq = len(storage.get_trace(run_id))
    for update in graph.stream(payload, _cfg(run_id), stream_mode="updates"):
        for node, delta in update.items():
            if node == "__interrupt__":
                continue
            for entry in (delta or {}).get("trace", []) or []:
                storage.add_trace(run_id, seq, entry)
                seq += 1
                if on_event:
                    on_event(entry)
    return _finish(run_id)


def _finish(run_id):
    graph = get_graph()
    snap = graph.get_state(_cfg(run_id))
    st = snap.values
    if snap.next:                      # paused at the approval checkpoint
        status = "awaiting_approval"
    elif st.get("letter"):
        status = "completed"
    elif st.get("approved") is False:
        status = "rejected"
    else:
        status = "failed" if any(f.get("severity") == "error" for f in st.get("findings", [])) else "completed"
    result = summarize(st)
    storage.update_run(run_id, status=status, result=result, approved_by=st.get("approver"),
                       finished_at=datetime.now().isoformat(timespec="seconds") if status != "awaiting_approval" else None)
    return {"run_id": run_id, "status": status, "result": result}


def summarize(st: dict) -> dict:
    calc = st.get("calc") or {}
    return {"case_id": st.get("case_id"), "result": calc.get("result"), "amount_usd": calc.get("amount_usd"),
            "laytime_commenced": calc.get("laytime_commenced"), "laytime_expired": calc.get("laytime_expired"),
            "completed": calc.get("completed"), "time_bar": calc.get("time_bar"),
            "valid_nor": (st.get("valid_nor") or {}).get("number"),
            "deductions": [{"reason": d["reason"], "kind": d.get("kind"), "hours": d["hours_applied"]}
                           for d in calc.get("deductions", []) if d["hours_applied"] > 0],
            "findings": st.get("findings", []), "corrections": st.get("corrections", []),
            "outputs": st.get("outputs")}


def start_run(case_id: str, auto_approve: bool = False, on_event: Callable | None = None) -> dict:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    storage.create_run(run_id, case_id, get_llm().label)
    try:
        return _stream(run_id, {"run_id": run_id, "case_id": case_id, "auto_approve": auto_approve, "trace": []},
                       on_event)
    except Exception as e:
        storage.update_run(run_id, status="failed", result={"error": repr(e)})
        raise


def decide(run_id: str, approved: bool, approver: str = "user", note: str = "",
           on_event: Callable | None = None) -> dict:
    """Resume a run paused at the approval checkpoint."""
    return _stream(run_id, Command(resume={"approved": approved, "approver": approver, "note": note}), on_event)


def get_state(run_id: str) -> dict:
    return get_graph().get_state(_cfg(run_id)).values


def get_run(run_id: str) -> dict | None:
    r = storage.get_run(run_id)
    if r:
        r["trace"] = storage.get_trace(run_id)
    return r
