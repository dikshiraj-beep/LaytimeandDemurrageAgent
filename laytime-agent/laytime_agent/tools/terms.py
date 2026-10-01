"""Charter-party terms the agent must establish, with retrieval queries, graders and extractors.

Each term goes through: retrieve -> grade each candidate chunk -> extract value -> resolve by precedence.
The LLM (if configured) grades and extracts; deterministic rules are the fallback and a cross-check.
"""
from __future__ import annotations

import re

from ..llm import get_llm

BINDING = {"recap", "rider", "charter_party"}          # negotiation emails are context only
SEARCH_TYPES = ["recap", "rider", "charter_party", "negotiation"]


def _norm(t: str) -> str:
    return " ".join(t.split())


def _num(s):
    return float(s.replace(",", ""))


def op_words(operation: str):
    return ("discharg", "load") if operation.startswith("disch") else ("load", "discharg")


# ------------------------------------------------------------------ term specifications
TERMS = {
    "laytime_rate": {
        "label": "Laytime rate and calendar",
        "queries": ["laytime rate tonnes per weather working day",
                    "{op_name} rate metric tonnes per weather working day {op_name} laytime",
                    "average rate of {op_name} per day Sundays holidays"],
        "fields": ["rate_mt_per_day", "calendar", "saturday_working", "rain_excluded", "ends_on_completion"],
    },
    "nor": {
        "label": "Notice of Readiness and laytime commencement",
        "queries": ["notice of readiness tender commencement of laytime",
                    "NOR tendered laytime to commence running hours after notice",
                    "notice of readiness port limits whether in port or not laytime commence"],
        "fields": ["place_required", "tender_window", "trigger"],
    },
    "demurrage": {
        "label": "Demurrage and despatch",
        "queries": ["demurrage rate per day pro rata despatch",
                    "demurrage USD per day despatch half working time saved",
                    "once on demurrage always on demurrage rate"],
        "fields": ["rate_usd_per_day", "despatch_fraction", "once_on_demurrage"],
    },
    "shifting": {
        "label": "Shifting anchorage to berth",
        "queries": ["shifting from anchorage to berth time count",
                    "time used in shifting to first berth shall not count laytime demurrage"],
        "fields": ["excluded_from_laytime", "excluded_on_demurrage"],
    },
    "strikes": {
        "label": "Strikes",
        "queries": ["strike stevedores time lost laytime", "strike lock-out port workers shall not count"],
        "fields": ["strike_excluded", "only_before_demurrage"],
    },
    "equipment": {
        "label": "Cargo gear breakdown",
        "queries": ["breakdown of equipment cranes time lost", "cargo gear shore cranes breakdown vessel equipment"],
        "fields": ["vessel_gear_breakdown_excluded", "vessel_gearless", "shore_equipment_excluded"],
    },
    "time_bar": {
        "label": "Claims time bar",
        "queries": ["demurrage claim time bar days supporting documents",
                    "claims presented in writing within days of completion of discharge"],
        "fields": ["days"],
    },
}


# ------------------------------------------------------------------ deterministic extractors
def extract_rules(term: str, text: str, ctx: dict) -> dict:
    t = _norm(text)
    tl = t.lower()
    v = {}
    if term == "laytime_rate":
        m = re.search(r"([\d,]{3,})\s*(?:metric tonnes|mt)\s*per\s*(?:weather working day|wwd)", t, re.I)
        if m:
            v["rate_mt_per_day"] = _num(m.group(1))
        if re.search(r"shex|sundays and holidays excepted", tl):
            v["calendar"] = "SHEX_UU" if re.search(r"unless used|\buu\b", tl) else "SHEX"
        elif re.search(r"shinc|sundays and holidays included", tl):
            v["calendar"] = "SHINC"
        if "saturday" in tl:
            v["saturday_working"] = "saturdays are working days" in tl
        if "weather working" in tl or "wwd" in tl or "prevented by rain" in tl:
            v["rain_excluded"] = True
        if "cease on completion" in tl:
            v["ends_on_completion"] = True
    elif term == "nor":
        if "port limits" in tl or "whether in port or not" in tl or "wipon" in tl:
            wipon = ("whether in port or not" in tl or "wipon" in tl) and "deleted" not in tl
            v["place_required"] = "anywhere" if wipon else "within_port_limits"
        m = re.search(r"between (\d{2}:\d{2}) and (\d{2}:\d{2})", t)
        if m:
            v["tender_window"] = [m.group(1), m.group(2)]
        m = re.search(r"(\d+)\s*running hours after", tl)
        noon = re.search(r"before noon.*?(\d{2}:\d{2}).*?after noon.*?(\d{2}:\d{2}) hours the next working day", tl)
        if noon:
            v["trigger"] = {"type": "noon_rule", "before_noon": noon.group(1), "after_noon_next_working_day": noon.group(2)}
        elif m:
            v["trigger"] = {"type": "hours_after_nor", "hours": int(m.group(1))}
    elif term == "demurrage":
        m = re.search(r"(?:usd|us\$)\s*([\d,]{4,})\s*(?:per day|pdpr|/day)", tl)
        if m:
            v["rate_usd_per_day"] = _num(m.group(1))
        if "half" in tl and "despatch" in tl:
            v["despatch_fraction"] = 0.5
        if "once on demurrage" in tl:
            v["once_on_demurrage"] = True
    elif term == "shifting":
        if "shifting" in tl and "shall not count" in tl:
            v["excluded_from_laytime"] = True
            v["excluded_on_demurrage"] = "time on demurrage" in tl
    elif term == "strikes":
        if "strike" in tl and "shall not count" in tl:
            v["strike_excluded"] = True
            v["only_before_demurrage"] = "already on demurrage" in tl
    elif term == "equipment":
        if "breakdown" in tl:
            v["vessel_gear_breakdown_excluded"] = bool(re.search(r"vessel'?s.{0,20}equipment|vessel'?s gear", tl)) \
                or "breakdown of vessel" in tl
            v["vessel_gearless"] = "gearless" in tl
            v["shore_equipment_excluded"] = bool(re.search(r"breakdown of shore|shore (cranes|equipment).{0,40}not count", tl))
    elif term == "time_bar":
        m = re.search(r"within\s*(\d{2,3})\s*days", tl)
        if m and ("claim" in tl or "time bar" in tl):
            v["days"] = int(m.group(1))
    return v


def grade_rules(term: str, chunk: dict, ctx: dict) -> tuple[bool, str]:
    """Is this chunk a binding source that actually governs the term for this operation?"""
    text = (chunk["title"] + " " + chunk["text"]).lower()
    if chunk["doc_type"] == "negotiation":
        return False, "negotiation email - offers/counters are not binding; use the clean recap / C/P"
    if chunk["doc_type"] not in BINDING:
        return False, f"{chunk['doc_type']} is not a contract term source"
    v = extract_rules(term, chunk["text"], ctx)
    if term == "laytime_rate":
        mine, other = op_words(ctx["operation"])
        title = chunk["title"].lower()
        has_mine, has_other = mine in text, other in text
        if mine in title and other not in title:
            pass
        elif other in title and mine not in title:
            return False, f"clause is about {'loading' if other == 'load' else 'discharging'}, not this operation"
        elif has_other and not has_mine:
            return False, f"clause is about {'loading' if other == 'load' else 'discharging'}, not this operation"
        if "rate_mt_per_day" not in v:
            return False, "no laytime rate found in this text"
        return True, "states the laytime rate for this operation"
    if term == "nor":
        if "notice of readiness" not in text and "nor" not in text.split():
            if not re.search(r"\bnor\b", text):
                return False, "does not deal with Notice of Readiness"
        if "trigger" not in v and "place_required" not in v:
            return False, "mentions NOR but sets no tender place or commencement rule"
        return True, "sets NOR tender conditions / laytime commencement"
    if term == "demurrage":
        if "rate_usd_per_day" not in v and "once_on_demurrage" not in v:
            return False, "no demurrage rate or rule here"
        return True, "states demurrage / despatch terms"
    ok = bool(v)
    return ok, ("governs this term" if ok else "does not govern this term")


# ------------------------------------------------------------------ LLM grader / extractor
FIELD_HELP = {
    "laytime_rate": 'rate_mt_per_day (number), calendar ("SHINC"|"SHEX"|"SHEX_UU"), saturday_working (bool), '
                    'rain_excluded (bool), ends_on_completion (bool)',
    "nor": 'place_required ("within_port_limits"|"anywhere"), tender_window (["HH:MM","HH:MM"] or null), '
           'trigger ({"type":"hours_after_nor","hours":n} or {"type":"noon_rule","before_noon":"HH:MM",'
           '"after_noon_next_working_day":"HH:MM"})',
    "demurrage": "rate_usd_per_day (number), despatch_fraction (number), once_on_demurrage (bool)",
    "shifting": "excluded_from_laytime (bool), excluded_on_demurrage (bool)",
    "strikes": "strike_excluded (bool), only_before_demurrage (bool)",
    "equipment": "vessel_gear_breakdown_excluded (bool), vessel_gearless (bool), shore_equipment_excluded (bool)",
    "time_bar": "days (integer)",
}


def grade_and_extract(term: str, chunk: dict, ctx: dict) -> dict:
    """Returns {relevant, reason, value, by, rules_value}. Uses the LLM when available."""
    rules_ok, rules_reason = grade_rules(term, chunk, ctx)
    rules_value = extract_rules(term, chunk["text"], ctx) if rules_ok else {}
    llm = get_llm()
    if not llm.available:
        return {"relevant": rules_ok, "reason": rules_reason, "value": rules_value, "by": "rules",
                "rules_value": rules_value}
    ans = llm.json(
        "You are a laytime and demurrage analyst grading retrieved charter-party text. Be strict: a clause is "
        "relevant only if it is a BINDING contract term (charter party, rider or clean fixture recap - never an "
        "offer/counter in a negotiation email) and it governs the requested term for the stated operation.",
        f"Operation at this port: {ctx['operation']}.\nTerm needed: {TERMS[term]['label']}.\n"
        f"Source document type: {chunk['doc_type']} ({chunk['ref']} - {chunk['title']}).\n"
        f"Text:\n\"\"\"{chunk['text']}\"\"\"\n\n"
        f'Return {{"relevant": true|false, "reason": "one sentence", "value": {{{FIELD_HELP[term]}}}}}. '
        "Only include value fields the text actually states.")
    if not isinstance(ans, dict) or "relevant" not in ans:
        return {"relevant": rules_ok, "reason": rules_reason + " (LLM unavailable, rules used)", "value": rules_value,
                "by": "rules", "rules_value": rules_value}
    value = ans.get("value") or {}
    if not isinstance(value, dict):
        value = {}
    # never let the LLM pick a negotiation email as binding
    relevant = bool(ans.get("relevant")) and chunk["doc_type"] in BINDING
    return {"relevant": relevant, "reason": ans.get("reason", ""), "value": value if relevant else {},
            "by": "llm", "rules_value": rules_value}


def rewrite_query(term: str, attempt: int, ctx: dict, rejected: list[str]) -> str:
    llm = get_llm()
    op_name = "discharging" if ctx["operation"].startswith("disch") else "loading"
    base = TERMS[term]["queries"][min(attempt, len(TERMS[term]["queries"]) - 1)].format(op_name=op_name)
    if llm.available and attempt > 0:
        q = llm.text("You rewrite search queries for a charter-party clause search engine. Reply with the query only.",
                     f"Term: {TERMS[term]['label']}. Operation: {op_name}. Previous results were rejected because: "
                     f"{'; '.join(rejected[-3:])}. Write a better short keyword query.", max_tokens=60)
        if q and 3 < len(q) < 200:
            return q.strip().strip('"')
    return base
