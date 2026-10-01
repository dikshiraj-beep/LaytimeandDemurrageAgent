"""Agent nodes: plan -> extract -> retrieve -> grade -> validate -> calculate -> verify -> approval -> draft.

Loops:
  A  grade    -> retrieve  : clause wrong/weak -> rewrite the query and retry
  B  validate -> extract   : evidence conflict -> re-read the sources (weather log, scans, AIS, deck log)
  C  verify   -> validate  : totals or citations fail -> route back and repair
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from langgraph.types import interrupt

from .. import config, storage
from ..llm import get_llm
from ..tools import documents as D
from ..tools import evidence as E
from ..tools import laytime as L
from ..tools import terms as T
from ..vectorstore import hybrid_search
from .state import AgentState, tr

FMT = D.FMT
CRITICAL_TERMS = ("laytime_rate", "nor", "demurrage")


def _dt(s):
    return datetime.strptime(s, FMT)


def _fname(doc_id):
    return doc_id.split("/", 1)[-1]


# ====================================================================== 1. PLAN
def plan(state: AgentState) -> dict:
    case = storage.one("SELECT * FROM cases WHERE case_id=?", (state["case_id"],)) or {}
    docs = storage.case_documents(state["case_id"])
    ctx = {"vessel": case.get("vessel"), "port": case.get("port"), "charterers": case.get("charterers"),
           "operation": (case.get("operation") or "").lower()}
    memory = storage.recall(ctx["charterers"], ctx["port"], ctx["vessel"])
    types = {d["doc_type"] for d in docs}
    n_nor = sum(1 for d in docs if d["doc_type"] == "nor")

    steps = [
        "Read the Statement of Facts and every Notice of Readiness; classify and pair all stoppages.",
        f"Retrieve and grade the {ctx['operation'] or 'cargo'} laytime terms: rate/calendar, NOR, demurrage, "
        "shifting, strikes, equipment, time bar.",
    ]
    if "recap" in types or "rider" in types:
        steps.append("A fixture recap/rider exists: check every term against it - it prevails over the printed C/P.")
    if "negotiation" in types:
        steps.append("Negotiation emails exist: treat offers/counters as non-binding context only.")
    if n_nor > 1:
        steps.append(f"{n_nor} NORs were tendered: validate each against the NOR clause; use the first valid one.")
    steps.append("Cross-check every rain stoppage against the independent port weather log.")
    if "image" in types:
        steps.append("Read image evidence (AIS track, signed SOF scan, deck log) and compare with the typed documents.")
    steps += ["Calculate laytime with the deterministic engine; verify independently; check the claims time bar.",
              "Pause for human approval, then draft the claim letter and record lessons in memory."]
    for m in memory:
        steps.append(f"Lesson from {m['source']} ({m['why']}): {m['lesson']}")

    llm = get_llm()
    trace = [tr("plan", "info", f"Case {state['case_id']}: {ctx['vessel']} - {ctx['operation']} at {ctx['port']}",
                {"documents": [f"{d['filename']} ({d['doc_type']})" for d in docs]}),
             tr("plan", "memory", f"Recalled {len(memory)} relevant past claims / lessons", memory)]
    if llm.available:
        ans = llm.json("You are a senior laytime analyst planning a demurrage claim review.",
                       f"Case facts: {json.dumps(ctx)}\nDocuments: {[d['filename'] + ' (' + d['doc_type'] + ')' for d in docs]}\n"
                       f"Lessons from memory: {json.dumps(memory)}\nDraft checklist: {json.dumps(steps)}\n"
                       'Improve the checklist (max 10 steps, keep lesson-driven checks). Return {"steps": [...]}')
        if isinstance(ans, dict) and isinstance(ans.get("steps"), list) and ans["steps"]:
            steps = [str(s) for s in ans["steps"]]
            trace.append(tr("plan", "llm", "Checklist refined by the LLM"))
    trace.append(tr("plan", "plan", "Checklist", steps))

    queries = {t: T.rewrite_query(t, 0, ctx, []) for t in T.TERMS}
    return {"ctx": ctx, "memory": memory, "plan": steps,
            "docs": [{k: d[k] for k in ("doc_id", "filename", "doc_type", "path", "precedence")} for d in docs],
            "pending_terms": list(T.TERMS), "attempts": {t: 0 for t in T.TERMS}, "queries": queries,
            "candidates": {}, "terms": {}, "unresolved": [], "reread_done": False, "reread_requests": [],
            "reread_results": [], "verify_attempts": 0, "verify_issues": [], "images": [], "trace": trace}


# ====================================================================== 2. EXTRACT (and loop-B re-read)
def extract(state: AgentState) -> dict:
    if state.get("reread_requests") and not state.get("reread_done"):
        return _reread(state)
    docs = state["docs"]
    trace = []
    sof_doc = next((d for d in docs if d["doc_type"] == "sof"), None)
    if not sof_doc:
        return {"trace": [tr("extract", "error", "No Statement of Facts found - cannot continue")]}
    sof = D.read_sof(sof_doc["path"])
    events, llm_used = D.classify_events(sof["events"])
    stoppages = D.pair_stoppages(events)
    ctx = dict(state["ctx"])
    ctx.update({k: sof[k] for k in ("vessel", "port", "berth", "bl_qty", "cargo", "charterers", "agents") if sof.get(k)})
    ctx["operation"] = "discharge" if sof["operation"].startswith("disch") else "load"
    trace.append(tr("extract", "tool", f"read_sof({sof_doc['filename']}): {len(events)} events, "
                                       f"{len(stoppages)} stoppage periods, B/L qty {sof['bl_qty']:,.0f} t",
                    {"events": [{"line": e["line"], "time": e["raw_time"], "type": e["type"], "text": e["text"]}
                                for e in events], "remarks": sof["remarks"]}))
    if llm_used:
        trace.append(tr("extract", "llm", "LLM classified unclear SOF entries"))

    nors = sorted((D.read_nor(d["path"]) for d in docs if d["doc_type"] == "nor"), key=lambda n: n["tendered"] or "")
    for n in nors:
        n["file"] = Path(n["source"]).name
    trace.append(tr("extract", "tool", f"read_nor: {len(nors)} notice(s) of readiness",
                    [{"no": n["number"], "tendered": n["tendered"], "position": n["position"], "file": n["file"]}
                     for n in nors]))

    images = []
    for d in docs:
        if d["doc_type"] == "image":
            r = E.read_image(d["path"])
            r["kind"] = r.get("image_type") or E.image_kind(d["path"])
            r["file"] = d["filename"]
            images.append(r)
            trace.append(tr("extract", "vision" if r.get("available") else "warning",
                            f"read_image({d['filename']}): {r.get('summary', '')[:160]}", r))
    return {"sof": {k: sof[k] for k in ("header", "remarks", "operation", "bl_qty")} | {"events": events},
            "stoppages": stoppages, "nors": nors, "images": images, "ctx": ctx, "trace": trace}


def _image(state, kind):
    return next((i for i in state.get("images", []) if i.get("kind") == kind or E.image_kind(i.get("path", "")) == kind), None)


def _reread(state: AgentState) -> dict:
    """Loop B: targeted second look at independent sources for each conflict raised by validate."""
    results, trace = [], [tr("extract", "loop", f"Loop B - re-reading sources for {len(state['reread_requests'])} "
                                                 f"conflict(s) raised by validation")]
    port, case_id = state["ctx"]["port"], state["case_id"]
    events = state["sof"]["events"]
    for req in state["reread_requests"]:
        res = {"request": req, "sources": []}
        if req["type"] == "nor_position":
            nor = next(n for n in state["nors"] if n["number"] == req["nor"])
            # second source 1: SOF arrival entry before the NOR
            arr = [e for e in events if e["type"] in ("ARRIVED", "ANCHORED") and e["ts"] and e["ts"] <= nor["tendered"]]
            if arr:
                pc = E.position_check(arr[-1]["text"], port)
                res["sources"].append({"source": f"SOF line {arr[-1]['line']}", "text": arr[-1]["text"], **pc})
            # second source 2: AIS screenshot (vision)
            ais = _image(state, "ais_track")
            if ais and get_llm().available:
                a = E.read_image(ais["path"], f"What latitude and longitude are shown for the NOR No. {req['nor']} marker "
                                              f"(tendered {nor['tendered']})? Also the AIS status at that time.")
                ll = E.parse_latlon(f"{a.get('quote', '')} {a.get('answer', '')}")
                if ll:
                    pc = E.position_check("", port, latlon=ll)
                    res["sources"].append({"source": f"AIS screenshot {ais['file']}", "text": a.get("answer"),
                                           "latlon": ll, **pc})
                else:
                    res["sources"].append({"source": f"AIS screenshot {ais['file']}", "text": a.get("answer"),
                                           "within": None, "method": "vision (no coordinates read)"})
            info = storage.port_info(port) or {}
            res["sources"].append({"source": "port_information.json", "text": info.get("port_limits", "")})
        elif req["type"] == "sof_chronology":
            s = state["stoppages"][req["idx"]]
            cand_end = (_dt(s["end"]) + timedelta(days=1)).strftime(FMT)
            w = E.rain_check(case_id, s["start"], cand_end) if s["cause"] == "rain" else None
            res["candidate_end"] = cand_end
            if w:
                res["sources"].append({"source": "port weather log", **w})
            scan = _image(state, "signed_sof")
            if scan and get_llm().available:
                a = E.read_image(scan["path"], f"On the line '{s['end_text']}' printed with time {s['end'][11:]}, what "
                                               "date is written, including any handwritten correction?")
                res["sources"].append({"source": f"signed SOF scan {scan['file']}", "text": a.get("answer"),
                                       "quote": a.get("quote")})
        elif req["type"] == "disputed_rain":
            s = state["stoppages"][req["idx"]]
            res["sources"].append({"source": "port weather log", **E.rain_check(case_id, s["start"], s["end"])})
            rem = E.disputed_in_remarks(state["sof"]["remarks"], s["start"])
            if rem:
                res["sources"].append({"source": "SOF Master's remarks", "text": rem})
            log_img = _image(state, "deck_log")
            if log_img and get_llm().available:
                a = E.read_image(log_img["path"], f"For {s['start'][:10]} between {s['start'][11:]} and {s['end'][11:]}, "
                                                  "what weather codes and remarks are logged? Was any rain recorded?")
                res["sources"].append({"source": f"deck log {log_img['file']}", "text": a.get("answer"),
                                       "quote": a.get("quote")})
        results.append(res)
        trace.append(tr("extract", "tool", f"Re-read for {req['type']} ({req.get('why', '')})", res))
    return {"reread_results": state.get("reread_results", []) + results, "reread_requests": [],
            "reread_done": True, "trace": trace}


# ====================================================================== 3. RETRIEVE
def retrieve(state: AgentState) -> dict:
    cands, trace = {}, []
    for t in state["pending_terms"]:
        att = state["attempts"][t]
        types = T.SEARCH_TYPES if att == 0 else sorted(T.BINDING)
        q = state["queries"][t]
        hits = hybrid_search(q, state["case_id"], types)
        cands[t] = hits
        trace.append(tr("retrieve", "tool", f"[{t}] attempt {att + 1}: '{q}' -> {len(hits)} chunks",
                        [{"chunk": f"{_fname(h['doc_id'])} {h['ref']}", "doc_type": h["doc_type"], "score": h["score"],
                          "dense_rank": h["dense_rank"], "bm25_rank": h["bm25_rank"]} for h in hits]))
    return {"candidates": cands, "trace": trace}


# ====================================================================== 4. GRADE (+ precedence resolution)
def _resolve(term, accepted):
    """Field-level merge: for each field take the value from the highest-precedence binding source."""
    accepted = sorted(accepted, key=lambda a: -a["precedence"])
    value, field_src, overrides = {}, {}, []
    for a in accepted:
        for f, v in a["value"].items():
            if v is None:
                continue
            src = f"{a['file']} {a['ref']}"
            if f not in value:
                value[f], field_src[f] = v, src
            elif value[f] != v:
                overrides.append({"field": f, "kept": value[f], "kept_from": field_src[f],
                                  "overridden": v, "overridden_from": src})
    return value, field_src, overrides


def grade(state: AgentState) -> dict:
    ctx, trace = state["ctx"], []
    terms, attempts, queries = dict(state["terms"]), dict(state["attempts"]), dict(state["queries"])
    pending, unresolved = [], list(state.get("unresolved", []))
    case_types = {d["doc_type"]: d["precedence"] for d in state["docs"] if d["doc_type"] in T.BINDING}
    for t in state["pending_terms"]:
        graded, accepted, rejected_reasons = [], [], []
        seen = set()

        def judge(chunks):
            for c in chunks:
                if c["chunk_id"] in seen:
                    continue
                seen.add(c["chunk_id"])
                g = T.grade_and_extract(t, c, ctx)
                item = {"file": _fname(c["doc_id"]), "ref": c["ref"], "doc_type": c["doc_type"],
                        "precedence": c["precedence"], "relevant": g["relevant"], "reason": g["reason"],
                        "value": g["value"], "by": g["by"]}
                if g["by"] == "llm" and g["relevant"] and g["rules_value"]:
                    diff = {k: (g["value"].get(k), v) for k, v in g["rules_value"].items()
                            if k in g["value"] and g["value"].get(k) != v}
                    if diff:
                        item["llm_vs_rules_disagreement"] = diff
                graded.append(item)
                if g["relevant"] and g["value"]:
                    accepted.append(item)
                else:
                    rejected_reasons.append(f"{item['file']} {item['ref']}: {g['reason']}")

        judge(state["candidates"].get(t, []))
        # precedence check: does a higher-ranking document (recap/rider) amend this term?
        if accepted:
            top = max(a["precedence"] for a in accepted)
            higher = [dt_ for dt_, p in case_types.items() if p > top]
            if higher:
                extra = hybrid_search(state["queries"][t], state["case_id"], higher, k=4)
                trace.append(tr("grade", "tool", f"[{t}] precedence check: searching {higher} for amendments",
                                [f"{_fname(h['doc_id'])} {h['ref']}" for h in extra]))
                judge(extra)
        trace.append(tr("grade", "grade", f"[{t}] {len([g for g in graded if g['relevant']])}/{len(graded)} "
                                          f"candidates relevant", graded))
        if accepted:
            value, field_src, overrides = _resolve(t, accepted)
            terms[t] = {"label": T.TERMS[t]["label"], "value": value, "field_sources": field_src,
                        "overrides": overrides, "attempts": attempts[t] + 1}
            msg = f"[{t}] resolved: {value}"
            trace.append(tr("grade", "resolved", msg, {"sources": field_src}))
            for o in overrides:
                trace.append(tr("grade", "precedence", f"[{t}] {o['field']}: {o['kept_from']} ({o['kept']}) prevails "
                                                       f"over {o['overridden_from']} ({o['overridden']})", o))
        else:
            attempts[t] += 1
            if attempts[t] < config.MAX_RETRIEVAL_ATTEMPTS:
                queries[t] = T.rewrite_query(t, attempts[t], ctx, rejected_reasons)
                pending.append(t)
                trace.append(tr("grade", "loop", f"Loop A - [{t}] no binding clause accepted; rewriting query to "
                                                 f"'{queries[t]}'", rejected_reasons[-4:]))
            else:
                unresolved.append(t)
                trace.append(tr("grade", "warning", f"[{t}] unresolved after {attempts[t]} attempts - flagged for "
                                                    "human review", rejected_reasons[-4:]))
    return {"terms": terms, "attempts": attempts, "queries": queries, "pending_terms": pending,
            "unresolved": unresolved, "trace": trace}


def route_after_grade(state: AgentState) -> str:
    return "retrieve" if state.get("pending_terms") else "validate"


# ====================================================================== 5. VALIDATE
def _val(state, term, field, default=None):
    return state["terms"].get(term, {}).get("value", {}).get(field, default)


def _src(state, term, field):
    return state["terms"].get(term, {}).get("field_sources", {}).get(field, "")


def _rr(state, rtype, **kw):
    for r in state.get("reread_results", []):
        q = r["request"]
        if q["type"] == rtype and all(q.get(k) == v for k, v in kw.items()):
            return r
    return None


def validate(state: AgentState) -> dict:
    ctx, port, case_id = state["ctx"], state["ctx"]["port"], state["case_id"]
    findings, corrections, requests, exclusions, counted = [], [], [], [], []
    trace = []
    can_reread = not state.get("reread_done")
    missing = [t for t in CRITICAL_TERMS if t not in state["terms"]]
    if missing:
        f = {"severity": "error", "text": f"Critical terms unresolved: {missing}. Cannot calculate."}
        return {"findings": [f], "exclusions": [], "trace": [tr("validate", "error", f["text"])]}

    # ---------------- NOR validity
    place = _val(state, "nor", "place_required", "anywhere")
    window = _val(state, "nor", "tender_window")
    valid_nor = None
    for n in state["nors"]:
        reasons, ok = [], True
        pc = E.position_check(n["position"], port)
        corro = _rr(state, "nor_position", nor=n["number"])
        if place == "within_port_limits":
            if pc["within"] is False:
                ok = False
                reasons.append(f"position '{n['position']}' is outside port limits ({pc.get('distance_nm', '?')} nm vs "
                               f"{pc.get('radius_nm', '?')} nm, {pc['method']}) but {_src(state, 'nor', 'place_required')} "
                               "requires NOR within port limits")
                if corro is None and can_reread:
                    requests.append({"type": "nor_position", "nor": n["number"],
                                     "why": f"NOR No. {n['number']} looks invalid - corroborate position from a second source"})
                elif corro:
                    agree = [s for s in corro["sources"] if s.get("within") is False]
                    reasons.append(f"corroborated by {len(agree)} independent source(s): "
                                   + "; ".join(f"{s['source']} ({s.get('distance_nm', '')} nm)" for s in agree))
            elif pc["within"] is None:
                reasons.append("position unclear - accepted but flagged for human review")
                findings.append({"severity": "warning", "text": f"NOR No. {n['number']}: position unclear"})
        if ok and window and n["tendered"]:
            hhmm = n["tendered"][11:]
            if not (window[0] <= hhmm <= window[1]):
                ok = False
                reasons.append(f"tendered at {hhmm}, outside the tender window {window[0]}-{window[1]}")
        n_res = {"number": n["number"], "tendered": n["tendered"], "file": n["file"], "valid": ok, "reasons": reasons}
        if ok and valid_nor is None:
            valid_nor = n_res
        if not ok:
            findings.append({"severity": "high", "text": f"NOR No. {n['number']} ({n['tendered']}) is INVALID: "
                                                          + "; ".join(reasons)})
    if valid_nor is None:
        return {"findings": findings + [{"severity": "error", "text": "No valid NOR found"}], "exclusions": [],
                "reread_requests": requests,
                "trace": [tr("validate", "error", "No valid NOR found", findings)]}

    # ---------------- commencement
    trig = _val(state, "nor", "trigger") or {}
    nt = _dt(valid_nor["tendered"])
    cal = _val(state, "laytime_rate", "calendar", "SHINC")
    sat = _val(state, "laytime_rate", "saturday_working", True)
    if trig.get("type") == "noon_rule":
        if nt.hour < 12:
            h, m = map(int, trig["before_noon"].split(":"))
            commence = nt.replace(hour=h, minute=m)
        else:
            h, m = map(int, trig["after_noon_next_working_day"].split(":"))
            commence = E.next_working_day(nt, port, cal, sat).replace(hour=h, minute=m)
        how = f"NOR {nt:%H:%M} {'before' if nt.hour < 12 else 'after'} noon -> noon rule"
    else:
        hrs = trig.get("hours", 0)
        commence = nt + timedelta(hours=hrs)
        how = f"NOR + {hrs} running hours"
        if not trig:
            findings.append({"severity": "warning", "text": "No laytime trigger found - laytime counted from NOR time"})
    commencement = {"time": commence.strftime(FMT), "how": how, "nor": valid_nor,
                    "clause": _src(state, "nor", "trigger")}
    completed = next((e for e in state["sof"]["events"] if e["type"] == "COMPLETED"), None)
    if not completed:
        return {"findings": findings + [{"severity": "error", "text": "No completion of cargo operations in SOF"}],
                "exclusions": [], "trace": [tr("validate", "error", "No completion event")]}
    commencement["completed"] = completed["ts"]
    commencement["completed_line"] = completed["line"]

    # ---------------- stoppages
    stoppages = []
    for idx, s in enumerate(state["stoppages"]):
        s = dict(s)
        if s["end"] is None:
            findings.append({"severity": "warning", "text": f"SOF line {s['start_line']}: stoppage never closed"})
            continue
        if _dt(s["end"]) <= _dt(s["start"]):
            cand = (_dt(s["end"]) + timedelta(days=1)).strftime(FMT)
            rr = _rr(state, "sof_chronology", idx=idx)
            if rr is None and can_reread:
                requests.append({"type": "sof_chronology", "idx": idx,
                                 "why": f"SOF lines {s['start_line']}-{s['end_line']}: end {s['end']} before start {s['start']}"})
                findings.append({"severity": "high", "text": f"SOF chronology error lines {s['start_line']}-{s['end_line']}: "
                                                              f"stoppage ends {s['end']} before it starts {s['start']}"})
                continue
            support = [x for x in (rr or {}).get("sources", [])
                       if x.get("verdict") == "rain" or (x.get("text") and cand[8:10] in str(x.get("text")))]
            if support:
                corrections.append({"what": f"SOF line {s['end_line']} end time", "from": s["end"], "to": cand,
                                    "evidence": "; ".join(x["source"] for x in support)})
                s["end"] = cand
                s["corrected"] = True
            else:
                findings.append({"severity": "high", "text": f"SOF lines {s['start_line']}-{s['end_line']}: chronology "
                                                              "error could not be corrected with evidence - period ignored"})
                continue
        stoppages.append((idx, s))

    for idx, s in stoppages:
        span = f"{s['start']} -> {s['end']}"
        ev = f"SOF lines {s['start_line']}-{s['end_line']}" + (" (corrected)" if s.get("corrected") else "")
        if s["cause"] == "rain":
            if not _val(state, "laytime_rate", "rain_excluded"):
                counted.append({"period": span, "cause": "rain", "why": "laytime terms do not exclude weather"})
                continue
            w = E.rain_check(case_id, s["start"], s["end"])
            if w["verdict"] == "dry":
                rr = _rr(state, "disputed_rain", idx=idx)
                if rr is None and can_reread:
                    requests.append({"type": "disputed_rain", "idx": idx,
                                     "why": f"SOF rain {span} but weather log shows no rain"})
                    continue
                srcs = ["port weather log: 0.0 mm"] + [x["source"] for x in (rr or {}).get("sources", [])
                                                       if x["source"] != "port weather log"]
                counted.append({"period": span, "cause": "rain (disputed)", "why": "no rain in independent evidence: "
                                + ", ".join(srcs), "sof": ev})
                findings.append({"severity": "high", "text": f"Rain stoppage {span} rejected - not supported by "
                                                              + ", ".join(srcs) + ". Time counts."})
                continue
            if w["verdict"] == "no_data":
                findings.append({"severity": "warning", "text": f"No weather data for {span}; SOF accepted"})
            exclusions.append({"start": s["start"], "end": s["end"], "kind": "rain",
                               "reason": "Rain - weather working days", "applies_on_demurrage": False,
                               "clause_ref": _src(state, "laytime_rate", "rain_excluded"),
                               "evidence": f"{ev}; weather log rain hours {', '.join(h[11:16] for h in w['rain_hours'])}"})
        elif s["cause"] == "strike":
            if _val(state, "strikes", "strike_excluded"):
                exclusions.append({"start": s["start"], "end": s["end"], "kind": "strike", "reason": "Strike of stevedores",
                                   "applies_on_demurrage": not _val(state, "strikes", "only_before_demurrage", True),
                                   "clause_ref": _src(state, "strikes", "strike_excluded"), "evidence": ev})
            else:
                counted.append({"period": span, "cause": "strike", "why": "no strike exception found"})
        elif s["cause"] == "breakdown":
            equip = s.get("equipment")
            if equip == "vessel" and _val(state, "equipment", "vessel_gear_breakdown_excluded"):
                exclusions.append({"start": s["start"], "end": s["end"], "kind": "breakdown",
                                   "reason": "Breakdown of vessel's gear", "applies_on_demurrage": True,
                                   "clause_ref": _src(state, "equipment", "vessel_gear_breakdown_excluded"), "evidence": ev})
            elif equip == "shore" and _val(state, "equipment", "shore_equipment_excluded"):
                exclusions.append({"start": s["start"], "end": s["end"], "kind": "breakdown",
                                   "reason": "Breakdown of shore equipment", "applies_on_demurrage": False,
                                   "clause_ref": _src(state, "equipment", "shore_equipment_excluded"), "evidence": ev})
            else:
                why = (f"{equip} equipment breakdown is not an excepted event "
                       f"({_src(state, 'equipment', 'vessel_gear_breakdown_excluded') or 'no exception clause'})")
                counted.append({"period": span, "cause": f"{equip} breakdown", "why": why, "sof": ev})
                findings.append({"severity": "info", "text": f"{span}: {why} - time counts"})
        else:
            counted.append({"period": span, "cause": s["cause"] or "other", "why": "not an excepted cause", "sof": ev})

    # ---------------- shifting anchorage -> first berth
    ev_list = state["sof"]["events"]
    sh = next((e for e in ev_list if e["type"] == "SHIFT_START"), None)
    af = next((e for e in ev_list if e["type"] == "ALL_FAST" and sh and e["ts"] >= sh["ts"]), None)
    if sh and af and _val(state, "shifting", "excluded_from_laytime"):
        exclusions.append({"start": sh["ts"], "end": af["ts"], "kind": "shifting",
                           "reason": "Shifting anchorage to first berth",
                           "applies_on_demurrage": bool(_val(state, "shifting", "excluded_on_demurrage")),
                           "clause_ref": _src(state, "shifting", "excluded_from_laytime"),
                           "evidence": f"SOF lines {sh['line']}-{af['line']}"})

    # ---------------- Sundays / holidays (SHEX, SHEX UU)
    if cal in ("SHEX", "SHEX_UU"):
        ops_start = next((e["ts"] for e in ev_list if e["type"] == "OPS_START"), None)
        worked = []
        if ops_start:
            stops = sorted((s["start"], s["end"]) for _, s in stoppages)
            cur = ops_start
            for a, b in stops:
                if a > cur:
                    worked.append((cur, min(a, completed["ts"])))
                cur = max(cur, b)
            if cur < completed["ts"]:
                worked.append((cur, completed["ts"]))
        for day in E.excepted_days(commencement["time"], completed["ts"], port, cal, sat):
            segs = [(day["start"], day["end"])]
            if cal == "SHEX_UU":
                for a, b in worked:
                    nxt = []
                    for x, y in segs:
                        if b <= x or a >= y:
                            nxt.append((x, y))
                        else:
                            if a > x:
                                nxt.append((x, a))
                            if b < y:
                                nxt.append((b, y))
                    segs = nxt
            if not segs:
                counted.append({"period": day["date"], "cause": day["name"], "why": "worked - counts (unless used)"})
            for x, y in segs:
                exclusions.append({"start": x, "end": y, "kind": "holiday",
                                   "reason": f"{day['name']} not worked - {cal.replace('_', ' ')}",
                                   "applies_on_demurrage": False,
                                   "clause_ref": _src(state, "laytime_rate", "calendar"),
                                   "evidence": f"port holiday calendar / weekday ({day['date']})"})

    # ---------------- loop C repair: drop anything the verifier could not support
    if state.get("verify_issues"):
        keep = []
        for e in exclusions:
            if not e.get("clause_ref") or not e.get("evidence") or _dt(e["end"]) <= _dt(e["start"]):
                findings.append({"severity": "high", "text": f"Removed unsupported exclusion '{e['reason']}' "
                                                              f"{e['start']}->{e['end']} (verification)"})
            else:
                keep.append(e)
        exclusions = keep
        trace.append(tr("validate", "loop", "Loop C - repaired exclusions after verification issues",
                        state["verify_issues"]))

    exclusions.sort(key=lambda e: e["start"])
    if requests:
        trace.append(tr("validate", "loop", f"Loop B - {len(requests)} conflict(s) need a second source", requests))
    for f in findings:
        trace.append(tr("validate", "finding", f["text"]))
    for c in corrections:
        trace.append(tr("validate", "correction", f"Corrected {c['what']}: {c['from']} -> {c['to']} "
                                                  f"(evidence: {c['evidence']})", c))
    trace.append(tr("validate", "info", f"Laytime commences {commencement['time']} ({how}, NOR No. "
                                        f"{valid_nor['number']}); {len(exclusions)} exclusions; "
                                        f"{len(counted)} stoppage(s) counted", {"exclusions": exclusions,
                                                                                 "counted": counted}))
    return {"findings": findings, "corrections": corrections, "reread_requests": requests, "valid_nor": valid_nor,
            "commencement": commencement, "exclusions": exclusions, "counted_periods": counted, "trace": trace}


def route_after_validate(state: AgentState) -> str:
    if any(f["severity"] == "error" for f in state.get("findings", [])) and not state.get("reread_requests"):
        return "approval"
    return "extract" if state.get("reread_requests") and not state.get("reread_done") else "calculate"


# ====================================================================== 6. CALCULATE
def calculate(state: AgentState) -> dict:
    rate = _val(state, "laytime_rate", "rate_mt_per_day")
    qty = state["ctx"]["bl_qty"]
    allowed_h = qty / rate * 24
    dem = _val(state, "demurrage", "rate_usd_per_day")
    calc = L.calculate(state["commencement"]["time"], state["commencement"]["completed"], allowed_h,
                       state["exclusions"], dem, _val(state, "demurrage", "despatch_fraction", 0.5))
    calc["allowance_basis"] = f"{qty:,.0f} t / {rate:,.0f} t per day = {allowed_h / 24:g} days"
    days = _val(state, "time_bar", "days")
    if days:
        bar = (_dt(calc["completed"]) + timedelta(days=days)).date()
        left = (bar - config.as_of_date()).days
        calc["time_bar"] = {"days": days, "deadline": bar.isoformat(), "days_left": left,
                            "clause": _src(state, "time_bar", "days"),
                            "status": "EXPIRED" if left < 0 else ("URGENT" if left <= config.TIME_BAR_WARNING_DAYS else "ok")}
    head = (f"{calc['result']}: USD {calc['amount_usd']:,.2f} "
            + (f"({calc['time_on_demurrage_hours']} h on demurrage)" if calc["result"] == "DEMURRAGE"
               else f"({calc['time_saved_hours']} h saved)"))
    return {"calc": calc, "trace": [tr("calculate", "tool", "laytime_calculator -> " + head, calc)]}


# ====================================================================== 7. VERIFY
def verify(state: AgentState) -> dict:
    calc, issues = state["calc"], L.verify(state["calc"], state["exclusions"])
    for t in CRITICAL_TERMS:
        if not state["terms"][t].get("field_sources"):
            issues.append(f"term {t} has no source citation")
    if calc["laytime_commenced"] < state["valid_nor"]["tendered"]:
        issues.append("laytime commences before the valid NOR")
    tb = calc.get("time_bar", {})
    warnings = []
    if tb.get("status") == "EXPIRED":
        warnings.append(f"Claim is TIME-BARRED since {tb['deadline']}")
    elif tb.get("status") == "URGENT":
        warnings.append(f"Time bar {tb['deadline']} - only {tb['days_left']} days left")
    trace = [tr("verify", "verify", "Independent re-computation and citation check: "
                + ("PASSED" if not issues else f"{len(issues)} issue(s)"), issues)]
    trace += [tr("verify", "warning", w) for w in warnings]
    n = state.get("verify_attempts", 0)
    if issues and n < config.MAX_VERIFY_ATTEMPTS:
        trace.append(tr("verify", "loop", "Loop C - routing back to validation to repair", issues))
    return {"verify_issues": issues, "verify_attempts": n + (1 if issues else 0), "trace": trace}


def route_after_verify(state: AgentState) -> str:
    if state.get("verify_issues") and state.get("verify_attempts", 0) <= config.MAX_VERIFY_ATTEMPTS:
        return "validate"
    return "approval"


# ====================================================================== 8. HUMAN APPROVAL (checkpoint)
def approval(state: AgentState) -> dict:
    if state.get("auto_approve"):
        return {"approved": True, "approver": "auto (evaluation mode)",
                "trace": [tr("approval", "approval", "Auto-approved (evaluation mode)")]}
    calc = state.get("calc") or {}
    decision = interrupt({"question": "Approve this laytime statement and draft the claim letter?",
                          "result": calc.get("result"), "amount_usd": calc.get("amount_usd"),
                          "findings": state.get("findings", [])})
    ok = bool((decision or {}).get("approved"))
    return {"approved": ok, "approver": (decision or {}).get("approver", "user"),
            "approval_note": (decision or {}).get("note", ""),
            "trace": [tr("approval", "approval", f"{'Approved' if ok else 'Rejected'} by "
                                                 f"{(decision or {}).get('approver', 'user')}",
                         decision)]}


def route_after_approval(state: AgentState) -> str:
    return "draft" if state.get("approved") and state.get("calc") else "end"


# ====================================================================== 9. DRAFT + MEMORY
def _cp_date(state):
    for d in state["docs"]:
        if d["doc_type"] == "charter_party":
            r = storage.one("SELECT text FROM documents WHERE doc_id=?", (d["doc_id"],))
            m = re.search(r"dated (\d{4}-\d{2}-\d{2})", r["text"] if r else "")
            if m:
                return m.group(1)
    return "(see charter party)"


def draft(state: AgentState) -> dict:
    ctx, calc = state["ctx"], state["calc"]
    run_dir = config.OUTPUT_DIR / state["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    applied = [d for d in calc["deductions"] if d["hours_applied"] > 0]
    ded = "\n".join(f"- {d['reason']}: {d['start']} -> {d['end']}, {d['hours_applied']:.2f} h "
                    f"({d['clause_ref']}; evidence: {d['evidence']})" for d in applied)
    if state.get("counted_periods"):
        ded += "\n\nPeriods recorded in the SOF that count as laytime:\n" + "\n".join(
            f"- {c['period']} ({c['cause']}): {c['why']}" for c in state["counted_periods"])
    if state.get("corrections"):
        ded += "\n\nCorrections to the Statement of Facts:\n" + "\n".join(
            f"- {c['what']}: {c['from']} -> {c['to']} (evidence: {c['evidence']})" for c in state["corrections"])
    invalid = [f["text"] for f in state.get("findings", []) if "INVALID" in f["text"]]
    if invalid:
        ded += "\n\nNotice of Readiness:\n" + "\n".join(f"- {t}" for t in invalid)
    is_dem = calc["result"] == "DEMURRAGE"
    vals = {
        "vessel": ctx["vessel"], "port": ctx["port"], "charterers": ctx["charterers"],
        "date": config.as_of_date().strftime("%d %B %Y"), "claim_ref": f"BOS-{state['run_id'][-6:].upper()}",
        "cp_date": _cp_date(state), "operation": "Discharge" if ctx["operation"] == "discharge" else "Loading",
        "laytime_allowed": f"{calc['laytime_allowed_hours']:.2f} hours ({calc['allowance_basis']})",
        "laytime_commenced": f"{calc['laytime_commenced']} ({state['commencement']['how']}, "
                             f"NOR No. {state['valid_nor']['number']})",
        "laytime_expired": calc.get("laytime_expired") or "not expired",
        "completed": calc["completed"],
        "time_on_demurrage": (f"{calc['time_on_demurrage_hours']:.2f} h on demurrage" if is_dem
                              else f"{calc['time_saved_hours']:.2f} h working time saved"),
        "rate": f"USD {calc['rate_usd_per_day']:,.2f} per day" + ("" if is_dem else " (despatch)"),
        "amount": f"USD {calc['amount_usd']:,.2f} " + ("due to Owners (demurrage)" if is_dem else "due to Charterers (despatch)"),
        "deductions_with_clause_references": "\n" + ded,
        "time_bar_clause": calc.get("time_bar", {}).get("clause") or "the charter party",
        "time_bar_date": calc.get("time_bar", {}).get("deadline", "n/a"),
    }
    tpl_path = config.SHARED_DIR / "demurrage_claim_letter_template.md"
    tpl = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "{{deductions_with_clause_references}}"
    letter = re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals.get(m.group(1), m.group(0))), tpl)
    llm = get_llm()
    trace = []
    if llm.available:
        polished = llm.text("You are a shipping claims manager. Polish the letter's wording for a professional tone. "
                            "Do NOT change any number, date, clause reference or amount. Return the full letter in Markdown.",
                            letter, max_tokens=2500)
        if polished and all(str(x) in polished for x in (f"{calc['amount_usd']:,.2f}", calc["laytime_commenced"])):
            letter = polished
            trace.append(tr("draft", "llm", "Letter wording polished by the LLM (figures checked unchanged)"))
        elif polished:
            trace.append(tr("draft", "warning", "LLM changed figures in the letter - kept the template version"))

    (run_dir / "claim_letter.md").write_text(letter, encoding="utf-8")
    statement = {"case_id": state["case_id"], "context": ctx, "terms": state["terms"], "commencement": state["commencement"],
                 "calculation": calc, "findings": state.get("findings", []), "corrections": state.get("corrections", []),
                 "counted_periods": state.get("counted_periods", []), "approved_by": state.get("approver")}
    (run_dir / "laytime_statement.json").write_text(json.dumps(statement, indent=2, default=str), encoding="utf-8")
    with open(run_dir / "laytime_statement.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from", "to", "reason", "hours_deducted", "applies_on_demurrage", "clause", "evidence", "status"])
        for d in calc["deductions"]:
            w.writerow([d["start"], d["end"], d["reason"], d["hours_applied"], d["applies_on_demurrage"],
                        d["clause_ref"], d["evidence"], d["status"]])

    # ---- memory: store a lesson for next time
    key = [f["text"] for f in state.get("findings", []) if f["severity"] in ("high", "error")]
    lesson = None
    if llm.available and key:
        lesson = llm.text("Write one short lesson (max 2 sentences) for future laytime claims with this counterparty/port.",
                          f"Port {ctx['port']}, charterers {ctx['charterers']}. Key findings: {key}", max_tokens=120)
    if not lesson and key:
        lesson = f"{ctx['port']} / {ctx['charterers'].split(',')[0]}: " + " | ".join(k[:140] for k in key[:3])
    if lesson:
        storage.add_lesson(ctx["charterers"], ctx["port"], ctx["vessel"], lesson.strip(), state["run_id"])
        trace.append(tr("draft", "memory", "Lesson saved to memory", lesson))
    trace.append(tr("draft", "output", f"Claim letter and laytime statement saved to outputs/{state['run_id']}/"))
    return {"letter": letter, "outputs": {"dir": str(run_dir.relative_to(config.ROOT)),
                                          "files": ["claim_letter.md", "laytime_statement.json",
                                                    "laytime_statement.csv"]}, "trace": trace}
