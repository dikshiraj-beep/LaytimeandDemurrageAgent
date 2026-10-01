"""REST API (FastAPI).  Run:  python run.py api   ->  http://127.0.0.1:8000/docs"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import config, ingest, service, storage
from .llm import get_llm

app = FastAPI(title="Laytime & Demurrage Claim Agent", version="1.0")


class RunRequest(BaseModel):
    case_id: str
    auto_approve: bool = False


class Decision(BaseModel):
    approved: bool
    approver: str = "api-user"
    note: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "llm": get_llm().label, "cases": len(storage.list_cases())}


@app.post("/ingest")
def run_ingest(reset: bool = False):
    return ingest.ingest(reset=reset)


@app.get("/cases")
def cases():
    return storage.list_cases()


@app.post("/runs")
def create_run(req: RunRequest):
    if not storage.one("SELECT 1 FROM cases WHERE case_id=?", (req.case_id,)):
        raise HTTPException(404, f"Unknown case {req.case_id}. Call POST /ingest first?")
    return service.start_run(req.case_id, auto_approve=req.auto_approve)


@app.get("/runs")
def runs():
    return storage.list_runs()


@app.get("/runs/{run_id}")
def run(run_id: str):
    r = service.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r


@app.post("/runs/{run_id}/decision")
def decision(run_id: str, d: Decision):
    r = storage.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    if r["status"] != "awaiting_approval":
        raise HTTPException(409, f"run is {r['status']}, not awaiting approval")
    return service.decide(run_id, d.approved, d.approver, d.note)


@app.get("/runs/{run_id}/letter", response_class=PlainTextResponse)
def letter(run_id: str):
    p = config.OUTPUT_DIR / run_id / "claim_letter.md"
    if not p.exists():
        raise HTTPException(404, "no letter yet (run not approved?)")
    return p.read_text(encoding="utf-8")
