"""Agent state shared by all nodes. Times are strings 'YYYY-MM-DD HH:MM' (local port time)."""
from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    case_id: str
    auto_approve: bool
    ctx: dict                 # vessel, port, operation, bl_qty, charterers ...
    plan: list                # checklist written by the planner
    memory: list              # recalled past claims / lessons
    docs: list                # documents available for this case
    sof: dict                 # parsed SOF (header, events, remarks)
    nors: list                # parsed NOR documents
    stoppages: list           # paired stoppage intervals from the SOF
    images: list              # image readings (vision)
    # retrieval / grading (loop A)
    pending_terms: list
    attempts: dict            # term -> attempts so far
    queries: dict             # term -> current query
    candidates: dict          # term -> graded candidate chunks
    terms: dict               # term -> resolved {value, sources, overrides}
    unresolved: list
    # validation (loop B)
    findings: list
    corrections: list
    reread_requests: list
    reread_results: list
    reread_done: bool
    valid_nor: dict
    commencement: dict
    exclusions: list
    counted_periods: list     # stoppages examined and found to COUNT (with reasons)
    # calculation + verification (loop C)
    calc: dict
    verify_issues: list
    verify_attempts: int
    # approval + output
    approved: bool
    approver: str
    approval_note: str
    letter: str
    outputs: dict
    trace: Annotated[list, operator.add]


def tr(node: str, kind: str, message: str, data: Any = None) -> dict:
    return {"ts": datetime.now().isoformat(timespec="seconds"), "node": node, "kind": kind,
            "message": message, "data": data}
