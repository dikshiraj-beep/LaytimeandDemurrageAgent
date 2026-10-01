"""Synthetic laytime cases + reference laytime engine (produces the answer key).

All vessels, companies, ports and people are fictional. Clause wording is
original and only modelled on common industry concepts (it is not BIMCO text).
"""
from datetime import datetime as DT, timedelta

def t(s):  # "2026-03-10 18:10"
    return DT.strptime(s, "%Y-%m-%d %H:%M")

OWNERS = "Bluewater Oceanic Shipping Pte. Ltd., Singapore"

# ---------------------------------------------------------------- CASE A
CASE_A = dict(
    id="A", difficulty="Easy",
    vessel="MV CORAL MERIDIAN", imo="9811204", flag="Singapore", dwt="63,450",
    charterers="Norcastle Grain Trading S.A., Geneva",
    cp_date="2026-01-22", cp_form="Voyage charter (company form BOS-VOY 2024)",
    cargo="45,000 metric tonnes wheat in bulk (5% more or less in Owners' option)",
    bl_qty=45000, operation="Discharge",
    load_port="Port Aldmere", port="Port Kestrel", berth="Berth 4, Grain Terminal",
    rate=8000, terms="WWD SHINC",
    dem=18000, des_fraction=0.5,
    laytime_trigger="12 running hours after tender of valid NOR",
    time_bar_days=365,
    agent="Kestrel Maritime Agencies Ltd.", master="Capt. R. Albarran",
    events=[
        ("2026-03-10 05:40", "Arrived Port Kestrel anchorage (within port limits) and dropped anchor"),
        ("2026-03-10 06:10", "Notice of Readiness tendered by email to Charterers and Agents"),
        ("2026-03-10 11:30", "Free pratique granted by radio"),
        ("2026-03-10 18:10", "Laytime commenced (NOR + 12 hours)"),
        ("2026-03-11 09:00", "Pilot on board"),
        ("2026-03-11 09:24", "Anchor aweigh, vessel shifting to berth"),
        ("2026-03-11 11:48", "All fast Berth 4 Grain Terminal"),
        ("2026-03-11 12:40", "Draft survey and hatch inspection completed"),
        ("2026-03-11 13:30", "Commenced discharging"),
        ("2026-03-12 14:00", "Rain - discharging suspended, hatches closed"),
        ("2026-03-12 17:30", "Rain stopped - hatches opened, discharging resumed"),
        ("2026-03-13 02:15", "Rain - discharging suspended, hatches closed"),
        ("2026-03-13 06:00", "Rain stopped - discharging resumed"),
        ("2026-03-15 20:00", "Rain - discharging suspended, hatches closed"),
        ("2026-03-15 22:30", "Rain stopped - discharging resumed"),
        ("2026-03-17 08:00", "Rain - discharging suspended, hatches closed"),
        ("2026-03-17 09:30", "Rain stopped - discharging resumed"),
        ("2026-03-18 10:25", "Completed discharging"),
        ("2026-03-18 12:10", "Final draft survey completed"),
        ("2026-03-18 14:00", "Cargo documents on board"),
        ("2026-03-18 14:40", "Pilot on board, vessel sailed"),
    ],
    commence="2026-03-10 18:10", complete="2026-03-18 10:25",
    exclusions=[  # start, end, reason, applies_on_demurrage
        ("2026-03-11 09:24", "2026-03-11 11:48", "Shifting anchorage to first berth (Cl. 7)", True),
        ("2026-03-12 14:00", "2026-03-12 17:30", "Rain - weather working days (Cl. 6)", False),
        ("2026-03-13 02:15", "2026-03-13 06:00", "Rain - weather working days (Cl. 6)", False),
        ("2026-03-15 20:00", "2026-03-15 22:30", "Rain - weather working days (Cl. 6)", False),
        ("2026-03-17 08:00", "2026-03-17 09:30", "Rain - weather working days (Cl. 6)", False),
    ],
    traps=[
        "C/P contains separate LOADING (Cl. 5) and DISCHARGING (Cl. 6) laytime clauses with different rates - agent must retrieve the discharge clause (8,000 MT/day), not the loading clause (10,000 MT/day).",
        "Rain on 17 March falls after laytime expired - once on demurrage always on demurrage, so it must NOT be deducted.",
        "Laytime ends at completion of discharge (Cl. 6), not when documents are on board or vessel sails.",
    ],
)

# ---------------------------------------------------------------- CASE B
CASE_B = dict(
    id="B", difficulty="Medium",
    vessel="MV ASTER HORIZON", imo="9790633", flag="Marshall Islands", dwt="81,200",
    charterers="Tresco Energy Resources Pte. Ltd., Singapore",
    cp_date="2026-03-30", cp_form="Voyage charter (company form BOS-VOY 2024)",
    cargo="60,000 metric tonnes steam coal in bulk (10% more or less in Owners' option)",
    bl_qty=60000, operation="Load",
    load_port="Halvard Bay", port="Halvard Bay", berth="Coal Berth 2",
    disch_port="Port Lindqvist",
    rate=15000, terms="WWD SHEX UU",
    dem=22000, des_fraction=0.5,
    laytime_trigger="NOR before noon: 13:00 same day; NOR after noon: 06:00 next working day",
    time_bar_days=365,
    agent="Halvard Shipping Services Co.", master="Capt. M. Rautio",
    events=[
        ("2026-04-29 15:20", "Arrived Halvard Bay Anchorage B (within port limits), anchored"),
        ("2026-04-29 15:35", "NOR tendered - berth occupied, vessel waiting (WIBON)"),
        ("2026-04-30 06:00", "Laytime commenced (NOR tendered after noon, 06:00 next working day)"),
        ("2026-04-30 06:00", "Vessel waiting at anchorage for berth"),
        ("2026-05-01 00:00", "Labour Day public holiday - no work, vessel waiting"),
        ("2026-05-02 06:30", "Pilot on board"),
        ("2026-05-02 07:00", "Anchor aweigh, shifting to berth"),
        ("2026-05-02 09:30", "All fast Coal Berth 2"),
        ("2026-05-02 10:15", "Commenced loading"),
        ("2026-05-02 16:00", "Rain - loading suspended"),
        ("2026-05-02 18:00", "Rain stopped - loading resumed"),
        ("2026-05-03 00:00", "Sunday - loading continued throughout (worked)"),
        ("2026-05-04 08:00", "Stevedore strike - loading stopped"),
        ("2026-05-04 14:00", "Strike ended - loading resumed"),
        ("2026-05-05 03:30", "Completed loading"),
        ("2026-05-05 05:00", "Draft survey completed"),
        ("2026-05-05 07:15", "Documents on board, vessel sailed"),
    ],
    commence="2026-04-30 06:00", complete="2026-05-05 03:30",
    exclusions=[
        ("2026-05-01 00:00", "2026-05-02 00:00", "Public holiday not worked - SHEX UU (Cl. 5)", False),
        ("2026-05-02 07:00", "2026-05-02 09:30", "Shifting anchorage to first berth (Cl. 7)", True),
        ("2026-05-02 16:00", "2026-05-02 18:00", "Rain - weather working days (Cl. 5)", False),
        ("2026-05-04 08:00", "2026-05-04 14:00", "Strike of stevedores (Cl. 16)", False),
    ],
    traps=[
        "Time waiting at anchorage for berth COUNTS (WIBON) - it is not excluded.",
        "1 May is a public holiday (see holiday calendar) and was not worked -> excluded; Sunday 3 May WAS worked -> counts in full under 'unless used'. Saturday is not excepted.",
        "Result is DESPATCH, not demurrage: loading finished before laytime expired. Despatch is half the demurrage rate on working time saved.",
    ],
)

# ---------------------------------------------------------------- CASE C
CASE_C = dict(
    id="C", difficulty="Hard",
    vessel="MV SEREN TALON", imo="9834571", flag="Liberia", dwt="38,900",
    charterers="Almadra Agro Inputs FZE, Dubai",
    cp_date="2026-05-06", cp_form="Voyage charter (company form BOS-VOY 2024) as amended by fixture recap",
    cargo="30,000 metric tonnes granular urea in bulk (5% more or less in Owners' option)",
    bl_qty=30000, operation="Discharge",
    load_port="Port Qaseem", port="Santa Rilla", berth="Berth 7, Bulk Fertiliser Terminal",
    rate=5000, terms="WWD SHINC",
    dem=14250, dem_printed=15000, des_fraction=0.5,
    laytime_trigger="6 running hours after tender of valid NOR (recap)",
    time_bar_days=120, time_bar_printed=90,
    agent="Rilla Port Agency S.A.", master="Capt. D. Okonjo",
    events=[
        ("2026-06-09 22:50", "Arrived outer roads, drifting approx. 14 nm off breakwater awaiting anchorage allocation"),
        ("2026-06-09 23:05", "NOR No. 1 tendered by email"),
        ("2026-06-10 16:20", "Anchored at customary Anchorage Alpha (within port limits)"),
        ("2026-06-10 16:45", "NOR No. 2 re-tendered by email"),
        ("2026-06-11 07:00", "Free pratique granted"),
        ("2026-06-12 04:50", "Pilot on board"),
        ("2026-06-12 05:30", "Anchor aweigh, shifting to berth"),
        ("2026-06-12 08:12", "All fast Berth 7"),
        ("2026-06-12 10:00", "Commenced discharging"),
        ("2026-06-13 13:10", "Rain - discharging suspended"),
        ("2026-06-13 16:40", "Rain stopped - discharging resumed"),
        ("2026-06-14 22:00", "Rain - discharging suspended"),
        ("2026-06-14 02:00", "Rain stopped - discharging resumed"),   # deliberate date typo (should be 15th)
        ("2026-06-15 09:00", "Shore crane No. 2 breakdown - discharging suspended"),
        ("2026-06-15 13:00", "Shore crane repaired - discharging resumed"),
        ("2026-06-16 10:30", "Rain - discharging suspended (see Master's remarks)"),
        ("2026-06-16 12:00", "Discharging resumed"),
        ("2026-06-19 15:20", "Completed discharging"),
        ("2026-06-19 18:00", "Documents on board, vessel sailed"),
    ],
    commence="2026-06-10 22:45", complete="2026-06-19 15:20",
    exclusions=[
        ("2026-06-12 05:30", "2026-06-12 08:12", "Shifting anchorage to first berth (Cl. 7)", True),
        ("2026-06-13 13:10", "2026-06-13 16:40", "Rain - weather working days (Cl. 6)", False),
        ("2026-06-14 22:00", "2026-06-15 02:00", "Rain - weather working days (Cl. 6); SOF end date corrected 14th -> 15th", False),
    ],
    traps=[
        "NOR No. 1 was tendered while drifting OUTSIDE port limits -> invalid under recap. Laytime runs from NOR No. 2 (16:45 on 10 June) + 6 hours = 22:45. Using NOR No. 1 would overstate the claim by roughly 17.7 hours.",
        "Negotiation trail: demurrage moved 15,000 (main terms, on subjects) -> 14,000 (Charterers' counter) -> 14,250 (final, confirmed when subjects lifted). Agent must use the final agreed figure from the clean recap, not an earlier negotiation email.",
        "Recap prevails over printed C/P:demurrage USD 14,250/day (not 15,000); time bar 120 days (not 90); laytime trigger 6 hours (not 12).",
        "SOF data error: rain stop recorded as '14/06/2026 02:00' - earlier than its start. Weather log confirms rain 22:00 on 14th to 02:00 on 15th; agent must detect and correct.",
        "Disputed rain 16 June 10:30-12:00: Master's remark says no rain on board and the port weather log shows 0.0 mm -> NOT excluded, counts as laytime.",
        "Shore crane breakdown is not an excepted event under the C/P (only breakdown of vessel's gear is) -> time counts.",
        "Time bar: claim due within 120 days of completion of discharge = 2026-10-17. Using the printed 90 days would wrongly conclude the claim is already time-barred.",
    ],
)

CASES = [CASE_A, CASE_B, CASE_C]


def compute(case):
    """Minute-by-minute reference laytime engine."""
    start, end = t(case["commence"]), t(case["complete"])
    allowed_h = case["bl_qty"] / case["rate"] * 24
    exc = [(t(a), t(b), r, d) for a, b, r, d in case["exclusions"]]
    used = 0  # minutes
    allowed_m = round(allowed_h * 60)
    expiry = None
    dem_m = 0
    applied = {}
    m = start
    while m < end:
        on_dem = used >= allowed_m
        hit = None
        for a, b, r, d in exc:
            if a <= m < b and (d or not on_dem):
                hit = r
                break
        if hit:
            applied[hit] = applied.get(hit, 0) + 1
        elif on_dem:
            dem_m += 1
        else:
            used += 1
            if used == allowed_m:
                expiry = m + timedelta(minutes=1)
        m += timedelta(minutes=1)
    res = dict(
        laytime_allowed_hours=round(allowed_h, 4),
        laytime_commenced=case["commence"],
        completed=case["complete"],
        deductions=[{"reason": k, "hours": round(v / 60, 4)} for k, v in applied.items()],
        laytime_used_hours=round(used / 60, 4),
    )
    rate = case["dem"]
    if dem_m:
        days = dem_m / 60 / 24
        res.update(result="DEMURRAGE", laytime_expired=expiry.strftime("%Y-%m-%d %H:%M"),
                   time_on_demurrage_hours=round(dem_m / 60, 4),
                   time_on_demurrage_days=round(days, 6),
                   rate_usd_per_day=rate, amount_usd=round(days * rate, 2))
    else:
        saved = (allowed_m - used) / 60
        drate = rate * case["des_fraction"]
        res.update(result="DESPATCH", time_saved_hours=round(saved, 4),
                   time_saved_days=round(saved / 24, 6),
                   rate_usd_per_day=drate, amount_usd=round(saved / 24 * drate, 2))
    res["claim_time_bar"] = (end + timedelta(days=case["time_bar_days"])).strftime("%Y-%m-%d")
    return res


if __name__ == "__main__":
    import json
    for c in CASES:
        print(c["id"], json.dumps(compute(c), indent=1))
