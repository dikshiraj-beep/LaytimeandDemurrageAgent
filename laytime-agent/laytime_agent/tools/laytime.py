"""Deterministic laytime calculator + an independent verifier.

Arithmetic is never left to the LLM: the agent decides WHICH periods count, this module counts them.
"""
from __future__ import annotations

from datetime import datetime, timedelta

FMT = "%Y-%m-%d %H:%M"


def _dt(s):
    return datetime.strptime(s, FMT)


def calculate(commence: str, complete: str, allowed_hours: float, exclusions: list[dict],
              demurrage_rate: float, despatch_fraction: float = 0.5) -> dict:
    """Minute-by-minute engine. Exclusion = {start, end, reason, applies_on_demurrage, ...}.
    Before expiry every exclusion stops the clock; after expiry ('once on demurrage, always on demurrage')
    only exclusions with applies_on_demurrage=True do."""
    start, end = _dt(commence), _dt(complete)
    allowed_m = round(allowed_hours * 60)
    exc = [(_dt(e["start"]), _dt(e["end"]), i, e.get("applies_on_demurrage", False)) for i, e in enumerate(exclusions)]
    used = dem = 0
    applied = [0] * len(exclusions)
    expiry = None
    m = start
    while m < end:
        on_dem = used >= allowed_m
        hit = next((i for a, b, i, d in exc if a <= m < b and (d or not on_dem)), None)
        if hit is not None:
            applied[hit] += 1
        elif on_dem:
            dem += 1
        else:
            used += 1
            if used == allowed_m:
                expiry = m + timedelta(minutes=1)
        m += timedelta(minutes=1)
    deductions = []
    for e, mins in zip(exclusions, applied):
        deductions.append({**e, "hours_applied": round(mins / 60, 4),
                           "status": "applied" if mins else "not applied (on demurrage or outside laytime)"})
    res = {"laytime_allowed_hours": round(allowed_hours, 4), "laytime_commenced": commence, "completed": complete,
           "laytime_used_hours": round(used / 60, 4), "deductions": deductions,
           "total_elapsed_hours": round((end - start).total_seconds() / 3600, 4)}
    if dem:
        days = dem / 1440
        res.update(result="DEMURRAGE", laytime_expired=expiry.strftime(FMT) if expiry else None,
                   time_on_demurrage_hours=round(dem / 60, 4), time_on_demurrage_days=round(days, 6),
                   rate_usd_per_day=demurrage_rate, amount_usd=round(days * demurrage_rate, 2))
    else:
        saved = (allowed_m - used) / 60
        rate = demurrage_rate * despatch_fraction
        res.update(result="DESPATCH", laytime_expired=None, time_saved_hours=round(saved, 4),
                   time_saved_days=round(saved / 24, 6), rate_usd_per_day=rate,
                   amount_usd=round(saved / 24 * rate, 2))
    return res


def _merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _overlap(intervals, a, b):
    return sum((max(timedelta(0), min(y, b) - max(x, a)) for x, y in intervals), timedelta(0))


def verify(calc: dict, exclusions: list[dict]) -> list[str]:
    """Independent check using interval arithmetic (a different method from the minute engine)."""
    issues = []
    start, end = _dt(calc["laytime_commenced"]), _dt(calc["completed"])
    if end <= start:
        return ["completion is before laytime commencement"]
    for e in exclusions:
        if _dt(e["end"]) <= _dt(e["start"]):
            issues.append(f"exclusion '{e['reason']}' ends before it starts ({e['start']} -> {e['end']})")
        if not e.get("clause_ref"):
            issues.append(f"exclusion '{e['reason']}' has no clause citation")
        if not e.get("evidence"):
            issues.append(f"exclusion '{e['reason']}' has no evidence citation")
    if issues:
        return issues
    allowed = timedelta(hours=calc["laytime_allowed_hours"])
    all_ex = _merge([(max(_dt(e["start"]), start), min(_dt(e["end"]), end)) for e in exclusions
                     if _dt(e["end"]) > start and _dt(e["start"]) < end])
    dem_ex = _merge([(max(_dt(e["start"]), start), min(_dt(e["end"]), end)) for e in exclusions
                     if e.get("applies_on_demurrage") and _dt(e["end"]) > start and _dt(e["start"]) < end])
    # find expiry by walking the merged exclusion gaps
    t, counted, expiry = start, timedelta(0), None
    for a, b in all_ex + [(end, end)]:
        if a > t:
            gap = a - t
            if counted + gap >= allowed:
                expiry = t + (allowed - counted)
                break
            counted += gap
        t = max(t, b)
    if expiry is None:
        used = counted + max(timedelta(0), end - t) if t < end else counted
        result = "DEMURRAGE" if used > allowed else "DESPATCH"
        dem = timedelta(0)
    else:
        dem = (end - expiry) - _overlap(dem_ex, expiry, end)
        result = "DEMURRAGE" if dem > timedelta(0) else "DESPATCH"
        used = allowed
    if result != calc["result"]:
        issues.append(f"result mismatch: engine {calc['result']} vs verifier {result}")
    elif result == "DEMURRAGE":
        h = dem.total_seconds() / 3600
        if abs(h - calc["time_on_demurrage_hours"]) > 1 / 60 + 1e-9:
            issues.append(f"demurrage time mismatch: engine {calc['time_on_demurrage_hours']} h vs verifier {h:.4f} h")
        amt = round(calc["time_on_demurrage_days"] * calc["rate_usd_per_day"], 2)
        if abs(amt - calc["amount_usd"]) > 0.01:
            issues.append("amount does not equal days x rate")
    else:
        h = used.total_seconds() / 3600
        if abs(h - calc["laytime_used_hours"]) > 1 / 60 + 1e-9:
            issues.append(f"laytime used mismatch: engine {calc['laytime_used_hours']} h vs verifier {h:.4f} h")
    return issues
