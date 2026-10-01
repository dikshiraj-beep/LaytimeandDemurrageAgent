"""Scores the agent (and a naive RAG baseline) against the answer key.

Run:  python run.py eval        -> prints a table and writes evals/report.md
The answer key lives here in evals/, outside data/, so the agent can never read it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from laytime_agent import service, storage  # noqa: E402
from laytime_agent.llm import get_llm  # noqa: E402

from evals.baseline import run_baseline  # noqa: E402

KEY = json.loads((ROOT / "evals" / "answer_key.json").read_text(encoding="utf-8"))
KIND_WORDS = {"shifting": "shifting", "rain": "rain", "holiday": "holiday", "strike": "strike"}


def kinds_from_key(deds):
    out = {}
    for d in deds:
        k = next((v for w, v in KIND_WORDS.items() if w in d["reason"].lower()), "other")
        out[k] = round(out.get(k, 0) + d["hours"], 2)
    return out


def kinds_from_calc(deds):
    out = {}
    for d in deds:
        h = d.get("hours_applied", d.get("hours", 0))
        if h > 0:
            k = d.get("kind") or "other"
            out[k] = round(out.get(k, 0) + h, 2)
    return out


def score(exp, got_result, got_amount, got_commenced, got_bar, got_kinds, got_nor=None):
    checks = {
        "result type": got_result == exp["result"],
        "amount (±USD 1)": got_amount is not None and abs(got_amount - exp["amount_usd"]) <= 1,
        "laytime commencement": got_commenced == exp["laytime_commenced"],
        "time-bar date": got_bar == exp["claim_time_bar"],
        "deductions by type": got_kinds == kinds_from_key(exp["deductions"]),
    }
    if exp["case"] == "C":
        checks["used valid NOR (No. 2)"] = got_nor == 2
    return checks


def case_folder(exp):
    vessel = exp["vessel"]
    c = storage.one("SELECT case_id FROM cases WHERE vessel=?", (vessel,))
    return c["case_id"] if c else None


def main():
    if not storage.list_cases():
        from laytime_agent import ingest
        print("Ingesting data first...")
        ingest.ingest(reset=True)
    lines = [f"# Evaluation report\n\nLLM: `{get_llm().label}`\n",
             "| Case | System | Result | Amount (USD) | Expected | Checks passed |", "|---|---|---|---|---|---|"]
    total = {"agent": [0, 0], "baseline": [0, 0]}
    detail = []
    for cid, exp in KEY.items():
        folder = case_folder(exp)
        r = service.start_run(folder, auto_approve=True)
        st = service.get_state(r["run_id"])
        calc = st.get("calc") or {}
        a = score(exp, calc.get("result"), calc.get("amount_usd"), calc.get("laytime_commenced"),
                  (calc.get("time_bar") or {}).get("deadline"), kinds_from_calc(calc.get("deductions", [])),
                  (st.get("valid_nor") or {}).get("number"))
        b_calc = run_baseline(folder)
        b = score(exp, b_calc["result"], b_calc["amount_usd"], b_calc["laytime_commenced"],
                  b_calc["time_bar"]["deadline"], kinds_from_calc(b_calc["deductions"]), b_calc["valid_nor"])
        for name, chk, c in (("agent", a, calc), ("baseline", b, b_calc)):
            total[name][0] += sum(chk.values())
            total[name][1] += len(chk)
            lines.append(f"| {cid} {exp['vessel']} | {name} | {c.get('result')} | {c.get('amount_usd', 0):,.2f} | "
                         f"{exp['result']} {exp['amount_usd']:,.2f} | {sum(chk.values())}/{len(chk)} |")
            detail.append(f"\n**Case {cid} - {name}** (run {r['run_id'] if name == 'agent' else 'baseline'})\n" +
                          "\n".join(f"- {'PASS' if v else 'FAIL'} {k}" for k, v in chk.items()))
    lines.append("")
    for name, (p, n) in total.items():
        lines.append(f"**{name}: {p}/{n} checks passed ({p / n:.0%})**  ")
    report = "\n".join(lines + ["\n## Details"] + detail)
    (ROOT / "evals" / "report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
