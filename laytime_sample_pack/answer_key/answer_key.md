# Answer Key - Laytime & Demurrage Sample Pack

Reference results computed minute-by-minute by `cases.py` (the generator's laytime engine). Keep this folder hidden from the agent during testing.

## Case A - MV CORAL MERIDIAN (Discharge, Port Kestrel) - Easy

| Item | Value |
|---|---|
| Laytime allowed | 135.0 h (5.625 days) |
| Laytime commenced | 2026-03-10 18:10 |
| Laytime expired | 2026-03-16 21:19 |
| Completed | 2026-03-18 10:25 |
| Time on demurrage | 37.1 h (1.545833 days) |
| Demurrage rate | USD 18,000/day |
| **Demurrage due to Owners** | **USD 27,825.00** |
| Claim time bar | 2027-03-18 |

**Deductions applied**

- Shifting anchorage to first berth (Cl. 7): 2.4 h
- Rain - weather working days (Cl. 6): 9.75 h

**Traps the agent should catch**

- C/P contains separate LOADING (Cl. 5) and DISCHARGING (Cl. 6) laytime clauses with different rates - agent must retrieve the discharge clause (8,000 MT/day), not the loading clause (10,000 MT/day).
- Rain on 17 March falls after laytime expired - once on demurrage always on demurrage, so it must NOT be deducted.
- Laytime ends at completion of discharge (Cl. 6), not when documents are on board or vessel sails.

## Case B - MV ASTER HORIZON (Load, Halvard Bay) - Medium

| Item | Value |
|---|---|
| Laytime allowed | 96.0 h (4 days) |
| Laytime commenced | 2026-04-30 06:00 |
| Completed | 2026-05-05 03:30 |
| Laytime used | 83.0 h |
| Working time saved | 13.0 h (0.541667 days) |
| Despatch rate | USD 11,000/day |
| **Despatch due to Charterers** | **USD 5,958.33** |
| Claim time bar | 2027-05-05 |

**Deductions applied**

- Public holiday not worked - SHEX UU (Cl. 5): 24.0 h
- Shifting anchorage to first berth (Cl. 7): 2.5 h
- Rain - weather working days (Cl. 5): 2.0 h
- Strike of stevedores (Cl. 16): 6.0 h

**Traps the agent should catch**

- Time waiting at anchorage for berth COUNTS (WIBON) - it is not excluded.
- 1 May is a public holiday (see holiday calendar) and was not worked -> excluded; Sunday 3 May WAS worked -> counts in full under 'unless used'. Saturday is not excepted.
- Result is DESPATCH, not demurrage: loading finished before laytime expired. Despatch is half the demurrage rate on working time saved.

## Case C - MV SEREN TALON (Discharge, Santa Rilla) - Hard

| Item | Value |
|---|---|
| Laytime allowed | 144.0 h (6 days) |
| Laytime commenced | 2026-06-10 22:45 |
| Laytime expired | 2026-06-17 08:57 |
| Completed | 2026-06-19 15:20 |
| Time on demurrage | 54.3833 h (2.265972 days) |
| Demurrage rate | USD 14,250/day |
| **Demurrage due to Owners** | **USD 32,290.10** |
| Claim time bar | 2026-10-17 |

**Deductions applied**

- Shifting anchorage to first berth (Cl. 7): 2.7 h
- Rain - weather working days (Cl. 6): 3.5 h
- Rain - weather working days (Cl. 6); SOF end date corrected 14th -> 15th: 4.0 h

**Traps the agent should catch**

- NOR No. 1 was tendered while drifting OUTSIDE port limits -> invalid under recap. Laytime runs from NOR No. 2 (16:45 on 10 June) + 6 hours = 22:45. Using NOR No. 1 would overstate the claim by roughly 17.7 hours.
- Negotiation trail: demurrage moved 15,000 (main terms, on subjects) -> 14,000 (Charterers' counter) -> 14,250 (final, confirmed when subjects lifted). Agent must use the final agreed figure from the clean recap, not an earlier negotiation email.
- Recap prevails over printed C/P:demurrage USD 14,250/day (not 15,000); time bar 120 days (not 90); laytime trigger 6 hours (not 12).
- SOF data error: rain stop recorded as '14/06/2026 02:00' - earlier than its start. Weather log confirms rain 22:00 on 14th to 02:00 on 15th; agent must detect and correct.
- Disputed rain 16 June 10:30-12:00: Master's remark says no rain on board and the port weather log shows 0.0 mm -> NOT excluded, counts as laytime.
- Shore crane breakdown is not an excepted event under the C/P (only breakdown of vessel's gear is) -> time counts.
- Time bar: claim due within 120 days of completion of discharge = 2026-10-17. Using the printed 90 days would wrongly conclude the claim is already time-barred.

**Image evidence - what the agent should read**

- `images/ais_track_screenshot.png`
  - Read: NOR No. 1 position 16°05.2'N 060°51.3'E at 09/06 23:05 LT, status Drifting; NOR No. 2 position 16°08.6'N 061°02.2'E at 10/06 16:45 LT, status At anchor.
  - Check: Distance from Rilla breakwater light (port_information.json): NOR 1 = 14.0 nm (> 5 nm port limits -> OUTSIDE); NOR 2 = 3.0 nm (inside), 0.14 nm from Anchorage Alpha centre (inside 1 nm radius).
  - Conclusion: Confirms NOR No. 1 invalid under the recap; laytime runs from NOR No. 2 + 6 h = 10/06 22:45.
- `images/sof_signed_scan.jpg`
  - Read: Three handwritten additions not in the typed SOF: (1) '14' struck through and corrected to '15' on the 02:00 rain-stopped line, initialled 'D.O. / RPA'; (2) agent's note 'vsl outside port limits - NOR 1 not accepted'; (3) Master's circled 16/06 10:30 rain line with 'NO RAIN on board - disputed'. Also 'Signed under protest - see LOP 19/06', agent's round stamp, Master's stamp, received stamp 19 Jun 2026 17:40.
  - Check: Compare scanned SOF against typed statement_of_facts.pdf line by line and list differences.
  - Conclusion: Signed SOF itself corrects the rain-stop date to 15/06 (evidence for the typo fix) and shows the port agent did not accept NOR No. 1. Signed SOF prevails over the unsigned typed copy.
- `images/deck_log_16jun2026.jpg`
  - Read: 16 June 2026, hours 10-11: weather code 'bc' (no rain code r/d/p), visibility 10 nm; remarks '10:30 Disch. STOPPED by receivers' order' and 'No rain / no precipitation'; Master's note disputing the SOF rain stoppage.
  - Check: Wind directions in the deck log match port_weather_log.csv for 16 June; precip 0.0 mm at 10:00 and 11:00.
  - Conclusion: Three independent sources (deck log, weather log, Master's SOF remark) agree there was no rain -> 10:30-12:00 on 16 June counts as laytime; it is not an excepted period.

## Extra checks across cases

- Weather logs contain light drizzle hours (Case A 14 Mar 03:00, Case C 17 Jun 01:00) with no work stoppage in the SOF - these must NOT be deducted.
- Case B: time waiting for berth counts as laytime, but laytime exceptions (the 1 May holiday) still apply during the wait.
- The past claims history contains lessons the agent's memory should surface (weather evidence for Norcastle, NOR position for Santa Rilla, time bar diarising).