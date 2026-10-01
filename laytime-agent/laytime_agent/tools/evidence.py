"""Evidence tools: weather log, holiday calendar, port limits (geo), Master's remarks and image reading."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from pathlib import Path

from .. import config, storage
from ..llm import get_llm
from .documents import FMT


def dt(s: str) -> datetime:
    return datetime.strptime(s, FMT)


# ------------------------------------------------------------------ weather
def rain_check(case_id: str, start: str, end: str) -> dict:
    """Did the independent port weather log record precipitation during [start, end)?"""
    hours = storage.weather_between(case_id, start, end)
    wet = [h for h in hours if (h["precip_mm"] or 0) > 0 and "RA" in (h["remarks"] or "")]
    drizzle = [h for h in hours if (h["precip_mm"] or 0) > 0 and "RA" not in (h["remarks"] or "")]
    return {"hours_checked": len(hours), "rain_hours": [h["ts"] for h in wet],
            "total_mm": round(sum(h["precip_mm"] for h in hours), 1),
            "drizzle_hours": [h["ts"] for h in drizzle],
            "verdict": "rain" if wet else ("no_data" if not hours else "dry")}


# ------------------------------------------------------------------ calendar
def holidays(port: str) -> dict:
    return {h["date"]: h["name"] for h in storage.holidays_for(port)}


def is_working_day(d: datetime, port: str, calendar: str, saturday_working: bool = True) -> bool:
    if calendar == "SHINC":
        return True
    if d.weekday() == 6 or d.strftime("%Y-%m-%d") in holidays(port):
        return False
    if d.weekday() == 5 and saturday_working is False:
        return False
    return True


def next_working_day(d: datetime, port: str, calendar: str, saturday_working=True) -> datetime:
    n = d + timedelta(days=1)
    while not is_working_day(n, port, calendar, saturday_working):
        n += timedelta(days=1)
    return n


def excepted_days(start: str, end: str, port: str, calendar: str, saturday_working=True) -> list[dict]:
    """Sundays / holidays inside [start, end] that the calendar term excepts."""
    if calendar == "SHINC":
        return []
    hol = holidays(port)
    out, d = [], dt(start).replace(hour=0, minute=0)
    while d <= dt(end):
        key = d.strftime("%Y-%m-%d")
        name = hol.get(key) or ("Sunday" if d.weekday() == 6 else None)
        if name is None and d.weekday() == 5 and saturday_working is False:
            name = "Saturday"
        if name:
            out.append({"date": key, "name": name, "start": d.strftime(FMT),
                        "end": (d + timedelta(days=1)).strftime(FMT)})
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------ ports / geo
def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    r = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_latlon(s: str):
    """'16°05.2'N 060°51.3'E' (or '16 05.2N', or decimal '16.0867N') -> (lat, lon) decimal."""
    s = s or ""
    vals = {}
    for d, mnt, h in re.findall(r"(\d{1,3})\s*(?:°|º|deg|\s)\s*(\d{1,2}(?:\.\d+)?)\s*['′’]?\s*([NSEW])\b", s):
        v = int(d) + float(mnt) / 60
        vals.setdefault("lat" if h in "NS" else "lon", -v if h in "SW" else v)
    if len(vals) < 2:
        for v, h in re.findall(r"(\d{1,3}\.\d+)\s*°?\s*([NSEW])\b", s):
            vals.setdefault("lat" if h in "NS" else "lon", -float(v) if h in "SW" else float(v))
    return (vals["lat"], vals["lon"]) if len(vals) == 2 else None


def position_check(position_text: str, port: str, latlon=None) -> dict:
    """Was the vessel within port limits? Uses coordinates if given, else the position wording."""
    info = storage.port_info(port) or {}
    radius = info.get("port_limits_radius_nm")
    ref = info.get(next((k for k in info if k.endswith("light")), ""), None)
    if latlon and ref and radius:
        d = haversine_nm(latlon[0], latlon[1], ref["lat"], ref["lon"])
        return {"within": d <= radius, "distance_nm": round(d, 1), "radius_nm": radius, "method": "coordinates"}
    t = position_text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*nm", t)
    if m and radius:
        d = float(m.group(1))
        return {"within": d <= radius, "distance_nm": d, "radius_nm": radius, "method": "stated distance"}
    if "within port limits" in t:
        return {"within": True, "method": "position wording"}
    for anch in info.get("customary_anchorages", []):
        name = anch.split("(")[0].strip().lower()
        if name and name in t:
            return {"within": "within port limits" in anch.lower(), "method": f"customary anchorage list ({anch})"}
    if "outer roads" in t or "outside port limits" in t:
        return {"within": False, "method": "position wording"}
    return {"within": None, "method": "unknown"}


# ------------------------------------------------------------------ Master's remarks
def disputed_in_remarks(remarks: str, start: str) -> str | None:
    """Return the remark sentence if the Master disputes a stoppage starting at `start`."""
    if not remarks:
        return None
    d = dt(start)
    tokens = [d.strftime("%d/%m/%Y %H:%M"), d.strftime("%d/%m/%Y") + " " + d.strftime("%H:%M")]
    for sent in re.split(r"\(\d\)", remarks):
        if "disput" in sent.lower() and any(tok in sent or d.strftime("%d/%m/%Y") in sent for tok in tokens):
            return sent.strip()
    return None


# ------------------------------------------------------------------ vision
VISION_PROMPT = (
    "You are reading shipping evidence for a laytime claim. Identify the image type: "
    "'ais_track' (vessel tracking map), 'signed_sof' (scanned statement of facts with handwriting/stamps), "
    "'deck_log' (ship's log page) or 'other'. Then extract:\n"
    "- ais_track: list of marked events with time, latitude, longitude (as written, e.g. 16°05.2'N 060°51.3'E) and status.\n"
    "- signed_sof: every handwritten annotation with the printed line it sits on, any handwritten date/time corrections, "
    "signatures and stamps.\n"
    "- deck_log: date, and for each hour: weather code, visibility, remarks; plus any Master's note.\n"
    'Return {"image_type": "...", "summary": "...", "events": [...], "annotations": [...], "hours": [...], "notes": [...]}')


def read_image(path: str, question: str | None = None) -> dict:
    llm = get_llm()
    p = config.ROOT / path
    if not llm.available:
        return {"available": False, "path": path,
                "summary": "Vision skipped: no LLM configured (mock mode). Text evidence used instead."}
    prompt = VISION_PROMPT if not question else (
        f"Answer this specific question about the image, quoting exactly what is written: {question}\n"
        'Return {"answer": "...", "quote": "...", "confidence": "high|medium|low"}')
    ans = llm.json("You extract facts from images of maritime documents. Never guess; say 'not visible' if unsure.",
                   prompt, images=[p], max_tokens=2500)
    if not isinstance(ans, dict):
        return {"available": False, "path": path, "summary": "Vision call failed; text evidence used instead."}
    ans["available"] = True
    ans["path"] = path
    return ans


def image_kind(path: str) -> str:
    n = Path(path).name.lower()
    if "ais" in n or "track" in n:
        return "ais_track"
    if "deck" in n or "log" in n:
        return "deck_log"
    if "sof" in n or "scan" in n:
        return "signed_sof"
    return "other"
