"""Generate the synthetic laytime & demurrage sample document pack."""
import csv, json, os, random, shutil
from datetime import timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether)
from cases import CASES, OWNERS, t, compute

OUT = "/home/claude/laytime_sample_pack"
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=15, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=ss["Heading3"], fontSize=10.5, spaceBefore=8, spaceAfter=3)
B = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12.2)
SM = ParagraphStyle("sm", parent=B, fontSize=7.5, leading=9.5, textColor=colors.grey)
CELL = ParagraphStyle("cell", parent=B, fontSize=8.3, leading=10.5)
BANNER = "SYNTHETIC SAMPLE DOCUMENT - fictional parties, vessels and ports - for AI agent testing only"


def pdf(path, story):
    def foot(c, d):
        c.saveState(); c.setFont("Helvetica", 7); c.setFillColor(colors.grey)
        c.drawString(18 * mm, 10 * mm, BANNER)
        c.drawRightString(192 * mm, 10 * mm, f"Page {d.page}")
        c.restoreState()
    SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=18 * mm).build(story, onFirstPage=foot, onLaterPages=foot)


def kv_table(rows, w=(48 * mm, 126 * mm)):
    tb = Table([[Paragraph(f"<b>{k}</b>", CELL), Paragraph(v, CELL)] for k, v in rows], colWidths=w)
    tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa7b4")),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f6")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return tb


def fmt(s):
    return t(s).strftime("%d/%m/%Y %H:%M")


def money(x):
    return f"USD {x:,.0f}" if x == int(x) else f"USD {x:,.2f}"


# ------------------------------------------------------------------ clauses
def clauses(c):
    """Printed charter party clauses. Case C printed terms are later amended by recap."""
    C = c["id"]
    dem = c.get("dem_printed", c["dem"])
    trig_hours = 12 if C in "AC" else None
    bar = c.get("time_bar_printed", c["time_bar_days"])
    cl = []
    cl.append(("1. Parties", f"It is agreed between <b>{OWNERS}</b> as Owners of the vessel described below, and "
               f"<b>{c['charterers']}</b> as Charterers, that the voyage shall be performed on the following terms."))
    cl.append(("2. Vessel", f"{c['vessel']}, IMO {c['imo']}, flag {c['flag']}, {c['dwt']} mt summer deadweight, "
               "single deck bulk carrier, holds clean and dry on arrival at the loading port."))
    cl.append(("3. Cargo", c["cargo"] + "."))
    if C == "B":
        cl.append(("4. Voyage", f"One safe berth, one safe port <b>{c['load_port']}</b> to load; one safe berth, "
                   f"one safe port <b>{c['disch_port']}</b> to discharge."))
    else:
        cl.append(("4. Voyage", f"One safe berth, one safe port <b>{c['load_port']}</b> to load; one safe berth, "
                   f"one safe port <b>{c['port']}</b> to discharge."))

    # Laytime clauses - deliberately two similar clauses (retrieval trap)
    if C == "A":
        cl.append(("5. Laytime - Loading", "Cargo to be loaded at the average rate of <b>10,000 metric tonnes per weather "
                   "working day of 24 consecutive hours, Sundays and holidays included (SHINC)</b>."))
        cl.append(("6. Laytime - Discharging", "Cargo to be discharged at the average rate of <b>8,000 metric tonnes per weather "
                   "working day of 24 consecutive hours, Sundays and holidays included (WWD SHINC)</b>. "
                   "Periods during which discharging is prevented by rain or other weather shall not count as laytime. "
                   "Laytime shall cease on completion of discharging."))
    elif C == "B":
        cl.append(("5. Laytime - Loading", "Cargo to be loaded at the average rate of <b>15,000 metric tonnes per weather working "
                   "day of 24 consecutive hours, Sundays and holidays excepted unless used (WWD SHEX UU)</b>; if used, actual "
                   "time used to count. Saturdays are working days. Periods during which loading is prevented by rain shall "
                   "not count. Laytime shall cease on completion of loading."))
        cl.append(("6. Laytime - Discharging", "Cargo to be discharged at the average rate of <b>20,000 metric tonnes per weather "
                   "working day, Sundays and holidays included (SHINC)</b>. Laytime shall cease on completion of discharging."))
    else:
        cl.append(("5. Laytime - Loading", "Cargo to be loaded at the average rate of <b>6,000 metric tonnes per weather working "
                   "day of 24 consecutive hours, SHINC</b>."))
        cl.append(("6. Laytime - Discharging", "Cargo to be discharged at the average rate of <b>5,000 metric tonnes per weather "
                   "working day of 24 consecutive hours, Sundays and holidays included (WWD SHINC)</b>. "
                   "Periods during which discharging is prevented by rain shall not count as laytime. "
                   "Laytime shall cease on completion of discharging."))

    cl.append(("7. Shifting", "Time used in shifting from the anchorage to the first loading or discharging berth shall not "
               "count as laytime <b>or as time on demurrage</b>. Any further shifting at Charterers' request shall count."))

    if C == "B":
        nor = ("Notice of Readiness may be tendered at any time day or night, Sundays and holidays included, "
               "<b>whether in berth or not (WIBON), whether in port or not (WIPON), whether in free pratique or not "
               "(WIFPON) and whether customs cleared or not (WCCON)</b>. If Notice of Readiness is tendered before noon, "
               "laytime shall commence at <b>13:00 hours the same day</b>; if tendered after noon, laytime shall commence at "
               "<b>06:00 hours the next working day</b>. Time lost waiting for berth shall count as laytime.")
    elif C == "A":
        nor = ("Notice of Readiness shall be tendered on arrival at the customary anchorage within port limits, between "
               "06:00 and 18:00 hours local time, any day. Laytime shall commence <b>12 running hours after tender of valid "
               "Notice of Readiness</b>, whether in berth or not (WIBON), whether in free pratique or not (WIFPON). "
               "Time lost waiting for berth shall count as laytime.")
    else:
        nor = ("Notice of Readiness may be tendered at any time day or night on arrival at or off the port, <b>whether in "
               "port or not (WIPON)</b>, whether in berth or not, whether in free pratique or not. Laytime shall commence "
               "<b>12 running hours after tender of Notice of Readiness</b>. Time lost waiting for berth shall count as laytime.")
    cl.append(("8. Notice of Readiness and Commencement of Laytime", nor))

    cl.append(("9. Demurrage and Despatch", f"Demurrage shall be paid by Charterers at the rate of <b>{money(dem)} per day "
               "or pro rata for part of a day</b>. Once the vessel is on demurrage, she shall remain on demurrage "
               "(\"once on demurrage, always on demurrage\"), save as expressly provided in Clause 7. Despatch money shall be "
               "paid by Owners at <b>half the demurrage rate on working time saved</b> at the loading and discharging ports."))
    cl.append(("10. Freight", "Freight payable 95% within five banking days of signing/releasing bills of lading, balance "
               "within 30 days of completion of discharge, less despatch or plus demurrage if agreed."))
    cl.append(("11. Agency", "Owners' agents at loading port; Charterers' agents at discharging port, paying customary fees."))
    cl.append(("12. Stevedores", "Cargo to be loaded, trimmed and discharged free of risk and expense to the vessel. "
               "Stevedores to be appointed and paid by Charterers."))
    cl.append(("13. Cargo Gear", "Vessel is gearless. Shore cranes/equipment to be provided by Charterers. "
               "Time lost due to breakdown of <b>vessel's</b> equipment shall not count as laytime or demurrage."))
    cl.append(("14. Bunkers", "Vessel to have liberty to bunker en route for Owners' account; time used not to count."))
    cl.append(("15. Ice", "Vessel not to be required to enter or remain at any ice-bound port."))
    cl.append(("16. Strikes", "Time lost by reason of strike or lock-out of stevedores or port workers shall not count as "
               "laytime, unless the vessel is already on demurrage."))
    cl.append(("17. War Risks", "Owners shall not be required to proceed to any port declared a war risk area."))
    cl.append(("18. General Average", "General average to be adjusted in London according to the York-Antwerp Rules 2016."))
    cl.append(("19. Commissions", "1.25% address commission to Charterers; 1.25% brokerage to Seahaven Chartering Ltd."))
    cl.append(("20. Claims Time Bar", f"Any claim for demurrage shall be presented in writing with all supporting documents "
               f"(Notice of Readiness, Statement of Facts and laytime calculation) within <b>{bar} days</b> of completion of "
               "discharge, failing which Charterers shall be discharged from all liability for such claim."))
    cl.append(("21. Law and Arbitration", "English law. London arbitration under LMAA Terms current at the time of reference."))
    return cl


def gen_cp(c, d):
    st = [Paragraph("VOYAGE CHARTER PARTY", H1),
          Paragraph(f"{c['cp_form']} - dated {c['cp_date']}", B), Spacer(1, 6),
          kv_table([("Owners", OWNERS), ("Charterers", c["charterers"]), ("Vessel", c["vessel"]),
                    ("Cargo", c["cargo"]), ("Brokers", "Seahaven Chartering Ltd., London")]),
          Spacer(1, 6)]
    if c["id"] == "C":
        st.append(Paragraph("<b>Note:</b> These printed terms are subject to the fixture recap of 06 May 2026, which "
                            "prevails in case of conflict.", B))
    for h, body in clauses(c):
        st.append(KeepTogether([Paragraph(h, H2), Paragraph(body, B)]))
    st += [Spacer(1, 14), Paragraph("For and on behalf of Owners: ____________________ &nbsp;&nbsp;&nbsp; "
                                    "For and on behalf of Charterers: ____________________", B)]
    pdf(f"{d}/charter_party.pdf", st)


def gen_recap(c, d):
    lines = [
        ("From", "Seahaven Chartering Ltd. (brokers)"), ("To", f"{OWNERS} / {c['charterers']}"),
        ("Date", "06 May 2026 17:42 (GMT)"), ("Subject", f"CLEAN FIXTURE RECAP - {c['vessel']} / {c['charterers'].split(',')[0]}"),
    ]
    body = [
        f"We are pleased to confirm the following clean fixture, all subjects lifted:",
        f"<b>Vessel:</b> {c['vessel']} (IMO {c['imo']})",
        f"<b>Cargo:</b> {c['cargo']}",
        f"<b>Load/Discharge:</b> 1 SB 1 SP {c['load_port']} / 1 SB 1 SP {c['port']}",
        "<b>Laycan:</b> 25-30 May 2026",
        "<b>Freight:</b> USD 31.75 per metric tonne FIOST",
        "<b>Load rate:</b> 6,000 MT per WWD SHINC",
        "<b>Discharge rate:</b> 5,000 MT per WWD SHINC",
        f"<b>Demurrage:</b> USD 14,250 per day pro rata / half despatch on working time saved (amends Cl. 9)",
        "<b>NOR (amends Cl. 8):</b> Notice of Readiness to be tendered <b>only upon arrival at the customary anchorage "
        "within the port limits</b> of the discharging port, WIBON / WIFPON / WCCON. The words \"whether in port or not\" "
        "are deleted. Laytime to commence <b>6 running hours</b> after tender of valid NOR.",
        "<b>Claims (amends Cl. 20):</b> demurrage claims to be presented with supporting documents within "
        "<b>120 days</b> of completion of discharge.",
        "Otherwise as per Owners' form BOS-VOY 2024 with logical amendments as per this recap. "
        "In case of conflict, this recap prevails over the printed form.",
        "Commission: 1.25% address + 1.25% Seahaven.",
        "Many thanks for the fixture.<br/>Best regards,<br/>J. Whitcombe - Dry Cargo Desk, Seahaven Chartering Ltd.",
    ]
    st = [Paragraph("EMAIL - FIXTURE RECAP", H1), kv_table(lines), Spacer(1, 8)]
    st += [Paragraph(x, B) for x in body]
    pdf(f"{d}/fixture_recap_email.pdf", st)


def gen_trail(c, d):
    """Pre-fixture negotiation email trail (Case C), oldest first."""
    OWN = "Chartering Desk, Bluewater Oceanic Shipping Pte. Ltd. (Owners)"
    CHT = "Chartering Desk, Almadra Agro Inputs FZE (Charterers)"
    BRK = "J. Whitcombe, Dry Cargo Desk, Seahaven Chartering Ltd. (Broker)"
    mails = [
        ("1", BRK, f"{OWN}; {CHT}", "04 May 2026 15:10 (GMT)",
         "MV SEREN TALON / ALMADRA - MAIN TERMS AGREED ON SUBJECTS",
         ["Further to today's negotiation, we confirm main terms agreed as follows, "
          "<b>subject to (1) Charterers' management approval and (2) receivers' approval of vessel, both to be lifted "
          "within 48 hours</b>, and subject to Owners' approval of Charterers' rider clauses:",
          "Vessel: MV SEREN TALON (IMO 9834571)",
          "Cargo: 30,000 mt granular urea in bulk, 5% more or less in Owners' option",
          "Load/Discharge: 1 SB 1 SP Port Qaseem / 1 SB 1 SP Santa Rilla",
          "Laycan: 25-30 May 2026",
          "Freight: USD 31.75 pmt FIOST",
          "Load/Discharge rates: 6,000 / 5,000 mt per WWD SHINC",
          "<b>Demurrage: USD 15,000 per day pro rata / half despatch working time saved</b>",
          "NOR / laytime: as per Owners' form BOS-VOY 2024",
          "Claims time bar: as per Owners' form",
          "Otherwise Owners' form BOS-VOY 2024 with logical amendments.",
          "Nothing further to follow at this stage. Please note that this is NOT a clean fixture."]),
        ("2", BRK, f"{OWN}; {CHT}", "05 May 2026 11:25 (GMT)",
         "RE: MV SEREN TALON / ALMADRA - CHARTERERS' RIDER COMMENTS",
         ["Charterers have reverted on the rider as follows, all other terms as per main terms of 04 May:",
          "1) <b>NOR:</b> Charterers cannot accept NOR tendered outside port limits at Santa Rilla owing to regular "
          "congestion at the outer roads. NOR to be tendered only on arrival at the customary anchorage within port "
          "limits; delete \"whether in port or not\". In exchange Charterers agree laytime to commence 6 running hours after "
          "valid NOR (instead of 12).",
          "2) <b>Demurrage:</b> Charterers counter at USD 14,000 per day pro rata.",
          "3) <b>Claims time bar:</b> Charterers require 120 days instead of 90 days to allow receivers' documents to be collated.",
          "Owners' comments please."]),
        ("3", BRK, f"{OWN}; {CHT}", "05 May 2026 16:40 (GMT)",
         "RE: MV SEREN TALON / ALMADRA - OWNERS' REPLY",
         ["Owners reply: points 1) and 3) accepted. Point 2) Owners counter <b>USD 14,250 per day pro rata</b>, "
          "half despatch working time saved.",
          "Understand Charterers accept 14,250 - please confirm. Main terms otherwise remain on subjects as per 04 May."]),
        ("4", BRK, f"{OWN}; {CHT}", "06 May 2026 16:05 (GMT)",
         "RE: MV SEREN TALON / ALMADRA - SUBJECTS LIFTED / CLEAN FIXTURE",
         ["We are pleased to advise that Charterers have confirmed demurrage USD 14,250 pdpr, "
          "<b>management approval and receivers' approval have been obtained and all subjects are lifted</b>.",
          "Owners have confirmed approval of Charterers' rider with the amendments agreed on 05 May.",
          "The vessel is now <b>clean fixed</b>. Full recap to follow shortly."]),
        ("5", BRK, f"{OWN}; {CHT}", "06 May 2026 17:42 (GMT)",
         "CLEAN FIXTURE RECAP - MV SEREN TALON / ALMADRA",
         ["[See separate file <i>fixture_recap_email.pdf</i> for the full recap text.]"]),
        ("6", OWN, BRK, "06 May 2026 18:20 (GMT)",
         "RE: CLEAN FIXTURE RECAP - MV SEREN TALON / ALMADRA",
         ["Thank you. Owners confirm the recap is <b>all in order</b>. Many thanks for the fixture.",
          "Please proceed to draw up the charter party. Our operations department will issue voyage orders to the Master.",
          "Regards, S. Tan - Chartering Manager, Bluewater Oceanic Shipping Pte. Ltd."]),
        ("7", CHT, BRK, "07 May 2026 09:05 (GMT)",
         "RE: CLEAN FIXTURE RECAP - MV SEREN TALON / ALMADRA",
         ["Good morning. Charterers confirm recap <b>all in order</b>. Please forward C/P for signature in due course.",
          "Regards, F. Haddad - Chartering, Almadra Agro Inputs FZE"]),
    ]
    st = [Paragraph("FIXTURE NEGOTIATION EMAIL TRAIL", H1),
          Paragraph(f"{c['vessel']} / Almadra Agro Inputs FZE - oldest message first. Exported from Owners' chartering mailbox.", B),
          Spacer(1, 6)]
    for n, frm, to, when, subj, body in mails:
        block = [Paragraph(f"Message {n}", H2),
                 kv_table([("From", frm), ("To", to), ("Date", when), ("Subject", subj)]), Spacer(1, 4)]
        block += [Paragraph(x, B) for x in body]
        st.append(KeepTogether(block))
    pdf(f"{d}/fixture_negotiation_emails.pdf", st)


def gen_nor(c, d, when, place, num=None, label=""):
    title = "NOTICE OF READINESS" + (f" No. {num}" if num else "")
    st = [Paragraph(title, H1), Spacer(1, 6),
          kv_table([("To", f"{c['charterers']} (Charterers) and receivers / shippers"),
                    ("C/O", c["agent"]), ("Vessel", f"{c['vessel']} (IMO {c['imo']})"),
                    ("Charter party dated", c["cp_date"]), ("Port", c["port"]),
                    ("Date / time tendered", f"{fmt(when)} local time"),
                    ("Vessel position", place), ("Method", "Email")]),
          Spacer(1, 10),
          Paragraph(f"Dear Sirs,<br/><br/>This is to notify you that the above vessel arrived at {c['port']} "
                    f"and is in all respects ready to {'load' if c['operation']=='Load' else 'discharge'} her cargo of "
                    f"{c['cargo']} in accordance with the terms and conditions of the charter party.{label}", B),
          Spacer(1, 18),
          Paragraph(f"Master: {c['master']} &nbsp;&nbsp;&nbsp;&nbsp; {c['vessel']}", B), Spacer(1, 16),
          Paragraph("NOR received: ____________________ &nbsp; Date/time: ____________ "
                    "&nbsp;&nbsp;(accepted subject to the terms, conditions and exceptions of the charter party)", B)]
    pdf(f"{d}/notice_of_readiness{'_' + str(num) if num else ''}.pdf", st)


def gen_sof(c, d):
    head = [("Vessel", f"{c['vessel']} (IMO {c['imo']})"), ("Port / berth", f"{c['port']} / {c['berth']}"),
            ("Operation", c["operation"]), ("Cargo", c["cargo"]),
            ("Bill of lading quantity", f"{c['bl_qty']:,} metric tonnes"),
            ("Charterers", c["charterers"]), ("Agents", c["agent"])]
    rows = [[Paragraph("<b>Date / time (LT)</b>", CELL), Paragraph("<b>Event</b>", CELL)]]
    for ts, ev in c["events"]:
        if "Laytime commenced" in ev:   # SOFs are factual; agent computes laytime itself
            continue
        rows.append([Paragraph(fmt(ts), CELL), Paragraph(ev, CELL)])
    tb = Table(rows, colWidths=(38 * mm, 136 * mm), repeatRows=1)
    tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa7b4")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe6ee")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st = [Paragraph("STATEMENT OF FACTS", H1), Paragraph(f"Issued by {c['agent']}", B), Spacer(1, 6),
          kv_table(head), Spacer(1, 8), tb, Spacer(1, 8)]
    if c["id"] == "C":
        st.append(Paragraph("<b>Master's remarks:</b> Signed under protest. (1) Vessel disputes the rain stoppage recorded "
                            "16/06/2026 10:30-12:00 - no rain was observed or logged on board during this period; discharging "
                            "was stopped by receivers' decision. (2) NOR No. 2 tendered without prejudice to NOR No. 1.", B))
    elif c["id"] == "B":
        st.append(Paragraph("<b>Remarks:</b> Loading continued throughout Sunday 03/05/2026. "
                            "No work on 01/05/2026 (public holiday).", B))
    else:
        st.append(Paragraph("<b>Remarks:</b> All times local. No remarks.", B))
    st += [Spacer(1, 18), Paragraph(f"Master: {c['master']} ____________ &nbsp;&nbsp;&nbsp; "
                                     f"For {c['agent']}: ____________", B)]
    pdf(f"{d}/statement_of_facts.pdf", st)


def gen_weather(c, d):
    rng = random.Random(ord(c["id"]))
    rain = [(t(a), t(b)) for a, b, r, _ in c["exclusions"] if r.startswith("Rain")]
    # rain that fell while on demurrage (Case A 17 Mar) is real weather too
    evs = c["events"]
    for i, (ts, ev) in enumerate(evs):
        if ev.startswith("Rain -") and "Master" not in ev:
            end = next(t(x) for x, e in evs[i + 1:] if "Rain stopped" in e)
            if end < t(ts):
                end += timedelta(days=1)
            if (t(ts), end) not in rain:
                rain.append((t(ts), end))
    drizzle = {"A": [t("2026-03-14 03:00")], "B": [], "C": [t("2026-06-17 01:00")]}[c["id"]]
    start = t(evs[0][0]).replace(hour=0, minute=0)
    stop = t(c["complete"]).replace(hour=23, minute=0)
    with open(f"{d}/port_weather_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station", "timestamp_local", "precip_mm", "wind_dir", "wind_kn", "visibility_nm", "remarks"])
        h = start
        while h <= stop:
            frac = sum(max(0, (min(b, h + timedelta(hours=1)) - max(a, h)).total_seconds()) for a, b in rain) / 3600
            p = round(frac * rng.uniform(1.6, 3.4), 1) if frac else (0.2 if h in drizzle else 0.0)
            rem = "RA" if frac else ("-DZ light drizzle" if h in drizzle else "")
            w.writerow([f"{c['port'].upper().replace(' ', '_')}_MET", h.strftime("%Y-%m-%d %H:%M"), p,
                        rng.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]), rng.randint(6, 22),
                        3 if frac else rng.choice([6, 8, 10]), rem])
            h += timedelta(hours=1)


# ------------------------------------------------------------------ shared docs
def gen_shared():
    s = f"{OUT}/shared"
    os.makedirs(s)
    with open(f"{s}/port_holidays_2026.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["port", "date", "holiday"])
        for r in [("Port Kestrel", "2026-01-01", "New Year's Day"), ("Port Kestrel", "2026-04-03", "Good Friday"),
                  ("Port Kestrel", "2026-12-25", "Christmas Day"),
                  ("Halvard Bay", "2026-01-01", "New Year's Day"), ("Halvard Bay", "2026-05-01", "Labour Day"),
                  ("Halvard Bay", "2026-05-14", "Ascension Day"), ("Halvard Bay", "2026-06-05", "Constitution Day"),
                  ("Halvard Bay", "2026-12-25", "Christmas Day"),
                  ("Santa Rilla", "2026-01-01", "New Year's Day"), ("Santa Rilla", "2026-06-24", "Harbour Festival"),
                  ("Santa Rilla", "2026-09-16", "Independence Day")]:
            w.writerow(r)
    ports = {
        "Port Kestrel": {"timezone": "UTC+02:00", "port_limits": "Within a 6 nm radius of Kestrel Point light",
                         "customary_anchorages": ["Kestrel Inner Anchorage (within port limits)"],
                         "pilotage": "Compulsory", "typical_shift_anchorage_to_berth_hours": 2.5},
        "Halvard Bay": {"timezone": "UTC+01:00", "port_limits": "Line joining Halvard Head and Skarn Point",
                        "customary_anchorages": ["Anchorage A", "Anchorage B (both within port limits)"],
                        "working_days": "Monday to Saturday; Sundays and public holidays are non-working unless worked",
                        "pilotage": "Compulsory", "typical_shift_anchorage_to_berth_hours": 2.5},
        "Santa Rilla": {"timezone": "UTC+04:00",
                        "port_limits": "Area within 5 nm of Rilla breakwater light; outer roads beyond this are OUTSIDE port limits",
                        "rilla_breakwater_light": {"lat": 16.166667, "lon": 61.083333, "display": "16°10.0'N 061°05.0'E"},
                        "port_limits_radius_nm": 5.0,
                        "customary_anchorages": ["Anchorage Alpha (within port limits)", "Anchorage Bravo (within port limits)"],
                        "anchorage_alpha": {"centre_lat": 16.141667, "centre_lon": 61.038333, "radius_nm": 1.0,
                                            "display": "centre 16°08.5'N 061°02.3'E, radius 1.0 nm"},
                        "anchorage_bravo": {"centre_lat": 16.105000, "centre_lon": 61.061667, "radius_nm": 1.0,
                                            "display": "centre 16°06.3'N 061°03.7'E, radius 1.0 nm"},
                        "notes": "During congestion vessels are instructed to drift at outer roads (10-15 nm off) until an anchorage is allocated.",
                        "pilotage": "Compulsory", "typical_shift_anchorage_to_berth_hours": 3.0},
    }
    json.dump(ports, open(f"{s}/port_information.json", "w"), indent=2)

    history = [
        {"claim_id": "BOS-DEM-2025-014", "vessel": "MV CORAL MERIDIAN", "counterparty": "Norcastle Grain Trading S.A.",
         "port": "Port Kestrel", "claimed_usd": 41200, "settled_usd": 38900, "status": "settled",
         "lessons": "Charterers rejected rain deductions until the port meteorological log was attached. Always attach weather evidence."},
        {"claim_id": "BOS-DEM-2025-031", "vessel": "MV ASTER HORIZON", "counterparty": "Tresco Energy Resources Pte. Ltd.",
         "port": "Halvard Bay", "claimed_usd": -7320, "settled_usd": -7320, "status": "settled (despatch paid by Owners)",
         "lessons": "Charterers accept Owners' laytime statement promptly when SHEX holidays are cited against the published port holiday calendar."},
        {"claim_id": "BOS-DEM-2025-047", "vessel": "MV SEREN TALON", "counterparty": "Almadra Agro Inputs FZE",
         "port": "Santa Rilla", "claimed_usd": 58750, "settled_usd": 44100, "status": "settled after dispute",
         "lessons": "Claim reduced because the first NOR was tendered at outer roads outside port limits and was invalid. "
                    "Check vessel position against port limits before accepting NOR time."},
        {"claim_id": "BOS-DEM-2026-006", "vessel": "MV CORAL MERIDIAN", "counterparty": "Kallos Feed Mills Ltd.",
         "port": "Port Aldmere", "claimed_usd": 12400, "settled_usd": 0, "status": "time-barred",
         "lessons": "Claim lost: submitted 4 days after the C/P time bar. Diarise time bar on completion of discharge."},
    ]
    json.dump(history, open(f"{s}/past_claims_history.json", "w"), indent=2)

    st = [Paragraph("COMPANY STANDARD LAYTIME TERMS & CLAIMS PROCEDURE", H1),
          Paragraph(f"{OWNERS} - Chartering & Claims Manual, Section 7 (rev. 2026)", B)]
    for h, body in [
        ("7.1 Standard positions", "Owners' preferred terms: NOR WIBON / WIPON / WIFPON / WCCON; laytime to commence 6 hours "
         "after NOR; shifting anchorage to berth to count as laytime; demurrage per day pro rata; despatch half demurrage on "
         "laytime saved; claims time bar not less than 90 days."),
        ("7.2 Hierarchy of documents", "Where a fixture recap conflicts with the printed charter party, the recap prevails. "
         "Rider clauses prevail over printed clauses. Always record which clause version was applied."),
        ("7.3 Validating the NOR", "Confirm the vessel was at the place required by the C/P when NOR was tendered (e.g. "
         "within port limits), within any tendering hours, and physically ready. If the first NOR is invalid, use the first "
         "valid re-tendered NOR. Do not rely on a charterers' 'accepted' stamp to cure an invalid NOR."),
        ("7.4 Weather deductions", "Deduct rain only where the SOF shows operations actually stopped due to weather, and "
         "cross-check against an independent weather log. Where SOF and Master disagree, rely on the weather log."),
        ("7.5 Once on demurrage", "After laytime expires, no further deductions apply except those the C/P expressly states "
         "apply to demurrage (e.g. shifting under some forms)."),
        ("7.6 Data quality", "Check the SOF for chronology errors (end before start, overlapping events, missing resumption "
         "entries). Correct only with supporting evidence and record the correction in the laytime statement."),
        ("7.7 Claim submission", "Submit claim letter, laytime statement, NOR(s), signed SOF and weather evidence. Diarise the "
         "time bar on completion of discharge and submit at least 14 days before it expires."),
    ]:
        st += [Paragraph(h, H2), Paragraph(body, B)]
    pdf(f"{s}/company_standard_laytime_terms.pdf", st)

    open(f"{s}/demurrage_claim_letter_template.md", "w").write("""# Demurrage / Despatch Claim - {{vessel}} - {{port}}

**To:** {{charterers}}
**From:** Bluewater Oceanic Shipping Pte. Ltd. - Claims Department
**Date:** {{date}}
**Our ref:** {{claim_ref}}

Dear Sirs,

**{{vessel}} - C/P dated {{cp_date}} - {{operation}} at {{port}}**

We refer to the above charter party and enclose our laytime statement for the vessel's call at {{port}}.

| Item | Value |
|---|---|
| Laytime allowed | {{laytime_allowed}} |
| Laytime commenced | {{laytime_commenced}} |
| Laytime expired | {{laytime_expired}} |
| Operations completed | {{completed}} |
| Time on demurrage / time saved | {{time_on_demurrage}} |
| Rate | {{rate}} |
| **Amount due** | **{{amount}}** |

Deductions applied: {{deductions_with_clause_references}}

Enclosed: laytime statement, Notice(s) of Readiness, signed Statement of Facts, port weather log.

We look forward to receiving your remittance within 30 days. This claim is submitted within the time bar under Clause {{time_bar_clause}} (deadline {{time_bar_date}}).

Yours faithfully,
Claims Department
Bluewater Oceanic Shipping Pte. Ltd.
""")


# ------------------------------------------------------------------ build
answer = {}
for c in CASES:
    d = f"{OUT}/case_{c['id']}_{c['vessel'].split(' ',1)[1].lower().replace(' ','_')}"
    os.makedirs(d)
    gen_cp(c, d)
    if c["id"] == "C":
        gen_recap(c, d)
        gen_trail(c, d)
        gen_nor(c, d, "2026-06-09 23:05", "Drifting at outer roads approx. 14 nm off Rilla breakwater", 1)
        gen_nor(c, d, "2026-06-10 16:45", "At anchor, Anchorage Alpha, Santa Rilla", 2,
                " This notice is tendered without prejudice to our Notice of Readiness No. 1 dated 09/06/2026 23:05.")
    else:
        nt = next(ts for ts, e in c["events"] if e.startswith("NOR") or e.startswith("Notice"))
        pos = next(e for ts, e in c["events"] if e.startswith("Arrived"))
        gen_nor(c, d, nt, pos.replace("Arrived ", "At "))
    gen_sof(c, d)
    gen_weather(c, d)
    r = compute(c)
    r.update(case=c["id"], difficulty=c["difficulty"], vessel=c["vessel"], port=c["port"],
             operation=c["operation"], traps_the_agent_should_catch=c["traps"])
    answer[c["id"]] = r

gen_shared()
os.makedirs(f"{OUT}/answer_key")
json.dump(answer, open(f"{OUT}/answer_key/answer_key.json", "w"), indent=2)
print(json.dumps({k: (v["result"], v["amount_usd"]) for k, v in answer.items()}))
