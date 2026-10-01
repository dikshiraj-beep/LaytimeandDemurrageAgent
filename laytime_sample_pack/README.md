# Laytime & Demurrage Agent - Synthetic Sample Pack

All companies, vessels, ports and people are **fictional**. Clause wording is original and only modelled on common industry concepts; it is not BIMCO or any other published form. Safe to use in demos, repos and hackathon submissions.

## Contents

| Folder | What's inside |
|---|---|
| `case_A_coral_meridian/` | **Easy** - wheat discharge, demurrage. Charter party, NOR, SOF, hourly port weather log |
| `case_B_aster_horizon/` | **Medium** - coal loading, SHEX UU, holiday, strike, result is **despatch** |
| `case_C_seren_talon/` | **Hard** - urea discharge, invalid first NOR, fixture recap overriding the C/P, SOF data error, disputed rain. Also includes the pre-fixture negotiation email trail (main terms on subjects, counters, subjects lifted, recap, both sides' "all in order"), plus an `images/` folder with image evidence |
| `shared/` | Port holiday calendar, port information (port limits, anchorages), company standard laytime terms, past claims history (seed for agent memory), claim letter template |
| `answer_key/` | Expected results (`answer_key.json` / `.md`) plus the generator scripts. **Hide this folder from the agent.** |

## Expected results

| Case | Result | Amount |
|---|---|---|
| A - Coral Meridian | Demurrage | USD 27,825.00 |
| B - Aster Horizon | Despatch | USD 5,958.33 |
| C - Seren Talon | Demurrage | USD 32,290.10 |

## How each file maps to an agent tool

| Tool the agent should call | Source file |
|---|---|
| Document parser / clause retriever | `charter_party.pdf`, `fixture_recap_email.pdf`, `fixture_negotiation_emails.pdf`, `company_standard_laytime_terms.pdf` |
| SOF event extractor | `statement_of_facts.pdf`, `notice_of_readiness*.pdf` |
| Weather lookup | `port_weather_log.csv` (hourly, local time) |
| Holiday / working-day calendar | `shared/port_holidays_2026.csv` |
| Port-limits check (NOR validity) | `shared/port_information.json` |
| Vision / image reader | `case_C_seren_talon/images/` - AIS track screenshot, scanned signed SOF, handwritten deck log |
| Long-term memory | `shared/past_claims_history.json` |
| Claim drafting | `shared/demurrage_claim_letter_template.md` |

## What each case tests

- **Retrieval grading:** every C/P has two similar laytime clauses (loading vs discharging) with different rates.
- **Document hierarchy:** Case C's recap overrides the printed demurrage rate, NOR clause, laytime trigger and time bar.
- **Negotiation vs final terms:** Case C's email trail shows demurrage at 15,000, then 14,000, then 14,250. Only the figure confirmed at "subjects lifted" and in the clean recap (14,250) is binding.
- **Self-correction:** Case C's SOF records a rain stop that ends before it starts; the weather log confirms the right date.
- **Evidence conflict:** Case C's agent SOF claims rain that the Master disputes and the weather log shows as dry.
- **Rule application:** once on demurrage (Case A), SHEX unless used and WIBON (Case B), shore vs vessel gear breakdown (Case C).
- **Image evidence (Case C):**
  - `ais_track_screenshot.png`: read the NOR positions, then compute the distance from the breakwater light in `port_information.json`. NOR 1 is 14.0 nm off (outside the 5 nm port limits); NOR 2 is inside Anchorage Alpha.
  - `sof_signed_scan.jpg`: compare with the typed SOF. The handwritten notes show the 14/06 -> 15/06 date correction, the agent's refusal of NOR 1, and the Master disputing the 16/06 rain.
  - `deck_log_16jun2026.jpg`: the handwritten log for 16 June shows no rain at 10:00-12:00, and the stoppage was on receivers' order.
- **Memory:** past claims history holds lessons relevant to each counterparty and port.

## Scoring suggestion

Score the agent on: correct result type and amount (within USD 1), correct laytime commencement, each deduction correctly included or rejected, time-bar date, and whether every figure in its laytime statement cites a clause or SOF line.
