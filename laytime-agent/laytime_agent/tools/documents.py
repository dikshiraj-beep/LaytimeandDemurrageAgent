"""Tools that read the factual documents: Statement of Facts (SOF) and Notices of Readiness (NOR)."""
from __future__ import annotations

import re
from datetime import datetime

import pdfplumber

from .. import config
from ..llm import get_llm

FMT = "%Y-%m-%d %H:%M"


def parse_dt(s: str) -> str | None:
    s = s.strip()
    for f in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(s[:16], f).strftime(FMT)
        except ValueError:
            continue
    m = re.search(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", s)
    return parse_dt(m.group(1)) if m else None


def _tables(path):
    with pdfplumber.open(config.ROOT / path) as pdf:
        tables, text = [], ""
        for p in pdf.pages:
            tables += p.extract_tables()
            text += (p.extract_text() or "") + "\n"
    return tables, text


# ------------------------------------------------------------------ SOF
def read_sof(path: str) -> dict:
    """Returns header fields, events in document order (with SOF line numbers) and the remarks text."""
    tables, text = _tables(path)
    header, events = {}, []
    for t in tables:
        if t and t[0] and (t[0][0] or "").lower().startswith("date"):
            for n, row in enumerate(t[1:], start=1):
                if len(row) >= 2 and row[0]:
                    events.append({"line": n, "raw_time": row[0].strip(), "ts": parse_dt(row[0]),
                                   "text": " ".join((row[1] or "").split())})
        else:
            for row in t:
                if len(row) >= 2 and row[0]:
                    header[row[0].strip()] = " ".join((row[1] or "").split())
    m = re.search(r"((?:Master's remarks|Remarks):.*?)(?:\nMaster:|\Z)", text, re.S)
    remarks = " ".join(m.group(1).split()) if m else ""
    qty = re.search(r"([\d,]+)\s*metric tonnes", header.get("Bill of lading quantity", ""))
    port_berth = header.get("Port / berth", "")
    return {
        "header": header,
        "vessel": header.get("Vessel", "").split("(")[0].strip(),
        "port": port_berth.split("/")[0].strip(),
        "berth": port_berth.split("/", 1)[1].strip() if "/" in port_berth else "",
        "operation": header.get("Operation", "").strip().lower(),   # "discharge" | "load"
        "cargo": header.get("Cargo", ""),
        "bl_qty": float(qty.group(1).replace(",", "")) if qty else None,
        "charterers": header.get("Charterers", ""),
        "agents": header.get("Agents", ""),
        "events": events,
        "remarks": remarks,
    }


# ------------------------------------------------------------------ NOR
def read_nor(path: str) -> dict:
    tables, text = _tables(path)
    kv = {}
    for t in tables:
        for row in t:
            if len(row) >= 2 and row[0]:
                kv[row[0].strip()] = " ".join((row[1] or "").split())
    num = re.search(r"NOTICE OF READINESS No\.\s*(\d+)", text)
    return {"number": int(num.group(1)) if num else 1,
            "tendered": parse_dt(kv.get("Date / time tendered", "")),
            "position": kv.get("Vessel position", ""),
            "port": kv.get("Port", ""),
            "without_prejudice": "without prejudice" in text.lower(),
            "source": path}


# ------------------------------------------------------------------ event classification
def classify_event(text: str) -> dict:
    t = text.lower()

    def stop(cause, **kw):
        return {"type": "STOP_START", "cause": cause, **kw}

    if t.startswith("arrived"):
        return {"type": "ARRIVED"}
    if "notice of readiness" in t or re.search(r"\bnor\b", t):
        return {"type": "NOR_TENDERED"}
    if "free pratique" in t:
        return {"type": "FREE_PRATIQUE"}
    if "anchor aweigh" in t:
        return {"type": "SHIFT_START"}
    if "all fast" in t:
        return {"type": "ALL_FAST"}
    if re.search(r"\bcommenced (loading|discharging)", t):
        return {"type": "OPS_START"}
    if re.search(r"\bcompleted (loading|discharging)", t):
        return {"type": "COMPLETED"}
    if "rain stopped" in t:
        return {"type": "STOP_END", "cause": "rain"}
    if "rain" in t and ("suspended" in t or "stopped" in t):
        return stop("rain", see_remarks="remarks" in t)
    if "strike ended" in t:
        return {"type": "STOP_END", "cause": "strike"}
    if "strike" in t:
        return stop("strike")
    if "repaired" in t:
        return {"type": "STOP_END", "cause": "breakdown"}
    if "breakdown" in t:
        equip = "shore" if "shore" in t else ("vessel" if ("vessel" in t or "ship" in t) else "unknown")
        return stop("breakdown", equipment=equip)
    if "resumed" in t:
        return {"type": "STOP_END", "cause": None}
    if "suspended" in t or "stopped" in t:
        return stop("other")
    if "anchored" in t:
        return {"type": "ANCHORED"}
    if "holiday" in t:
        return {"type": "NOTE", "note": "holiday"}
    if "sunday" in t:
        return {"type": "NOTE", "note": "sunday"}
    if "sailed" in t:
        return {"type": "SAILED"}
    return {"type": "INFO"}


def classify_events(events: list[dict]) -> tuple[list[dict], int]:
    """Heuristic classification; anything left as INFO but mentioning stoppage words goes to the LLM."""
    llm = get_llm()
    unclear = []
    for e in events:
        e.update(classify_event(e["text"]))
        if e["type"] == "INFO" and re.search(r"stop|delay|wait|suspend|interrupt|breakdown|weather", e["text"], re.I):
            unclear.append(e)
    used = 0
    if unclear and llm.available:
        ans = llm.json(
            "You classify Statement of Facts entries for laytime calculation.",
            "Classify each entry as one of ARRIVED, NOR_TENDERED, SHIFT_START, ALL_FAST, OPS_START, COMPLETED, "
            "STOP_START, STOP_END, INFO. For STOP_START give cause (rain|strike|breakdown|other). Return "
            '{"items":[{"line":n,"type":"...","cause":null}]}\n' +
            "\n".join(f'line {e["line"]}: {e["text"]}' for e in unclear))
        used = 1
        for it in (ans or {}).get("items", []):
            for e in unclear:
                if e["line"] == it.get("line") and it.get("type"):
                    e["type"], e["cause"] = it["type"], it.get("cause")
                    e["classified_by"] = "llm"
    return events, used


def pair_stoppages(events: list[dict]) -> list[dict]:
    """Pairs STOP_START with the next matching STOP_END in document order (not time order, so typos show)."""
    open_stops, out = [], []
    for e in events:
        if e["type"] == "STOP_START":
            open_stops.append(e)
        elif e["type"] == "STOP_END" and open_stops:
            idx = len(open_stops) - 1
            for i in range(len(open_stops) - 1, -1, -1):
                if e.get("cause") in (None, open_stops[i].get("cause")):
                    idx = i
                    break
            s = open_stops.pop(idx)
            out.append({"cause": s.get("cause"), "equipment": s.get("equipment"), "start": s["ts"], "end": e["ts"],
                        "start_line": s["line"], "end_line": e["line"], "start_text": s["text"], "end_text": e["text"],
                        "see_remarks": s.get("see_remarks", False)})
    for s in open_stops:
        out.append({"cause": s.get("cause"), "equipment": s.get("equipment"), "start": s["ts"], "end": None,
                    "start_line": s["line"], "end_line": None, "start_text": s["text"], "end_text": None,
                    "see_remarks": s.get("see_remarks", False)})
    return out
