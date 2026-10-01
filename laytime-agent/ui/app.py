"""Streamlit front end.   Run:  python run.py ui   ->  http://localhost:8501"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from laytime_agent import config, ingest, service, storage  # noqa: E402
from laytime_agent.llm import get_llm  # noqa: E402

st.set_page_config(page_title="Laytime & Demurrage Agent", page_icon="⚓", layout="wide")

ICON = {"plan": "🧭", "memory": "🧠", "tool": "🔧", "llm": "✨", "vision": "👁️", "grade": "⚖️", "resolved": "✅",
        "precedence": "📑", "loop": "🔁", "finding": "🚩", "correction": "✏️", "warning": "⚠️", "error": "⛔",
        "verify": "🔍", "approval": "🙋", "output": "📄", "info": "ℹ️"}
NODE_LABEL = {"plan": "1 Plan", "extract": "2 Extract", "retrieve": "3 Retrieve", "grade": "4 Grade",
              "validate": "5 Validate", "calculate": "6 Calculate", "verify": "6 Verify", "approval": "Approval",
              "draft": "Draft + memory"}


def line(e):
    return f"{ICON.get(e['kind'], '•')} **{NODE_LABEL.get(e['node'], e['node'])}** · {e['message']}"


# ------------------------------------------------------------------ sidebar
storage.init_db()
with st.sidebar:
    st.title("⚓ Laytime agent")
    st.caption(f"LLM: `{get_llm().label}`")
    if not get_llm().available:
        st.info("Mock mode: deterministic heuristics replace the LLM. Set LLM_PROVIDER and an API key in `.env` "
                "for grading, vision and drafting by a real model.")
    cases = storage.list_cases()
    if st.button("Ingest / rebuild index", width="stretch"):
        with st.spinner("Reading documents, chunking clauses, building vector index..."):
            stats = ingest.ingest(reset=True)
        st.success(f"{stats['documents']} documents, {stats['chunks']} chunks ({stats['embeddings']} embeddings)")
        cases = storage.list_cases()
    if not cases:
        st.warning("No cases loaded yet - click **Ingest / rebuild index**.")
        st.stop()
    labels = {c["case_id"]: f"{c['vessel']} - {c['operation']} at {c['port']}" for c in cases}
    case_id = st.selectbox("Claim case", list(labels), format_func=lambda k: labels[k])
    auto = st.checkbox("Auto-approve (skip human checkpoint)", value=False)
    run_clicked = st.button("▶ Run agent", type="primary", width="stretch")
    st.divider()
    st.caption("Previous runs")
    runs = storage.list_runs(15)
    for r in runs:
        if st.button(f"{r['case_id'].split('_')[1]} · {r['status']} · {r['run_id'][-6:]}", key=r["run_id"],
                     width="stretch"):
            st.session_state["run_id"] = r["run_id"]

st.header("Laytime & Demurrage Claim Agent")
st.caption("Plan → Extract → Retrieve → Grade → Validate → Calculate/Verify → Human approval → Claim letter")

# ------------------------------------------------------------------ run
if run_clicked:
    box = st.status(f"Running agent on {labels[case_id]} ...", expanded=True)
    out = service.start_run(case_id, auto_approve=auto, on_event=lambda e: box.markdown(line(e)))
    box.update(label=f"Run {out['run_id']} - {out['status']}", state="complete", expanded=False)
    st.session_state["run_id"] = out["run_id"]
    st.rerun()                      # refresh sidebar (previous runs) and show the full result

run_id = st.session_state.get("run_id")
if not run_id:
    c1, c2 = st.columns(2)
    c1.markdown("**Case documents**")
    c1.dataframe(pd.DataFrame(storage.case_documents(case_id))[["filename", "doc_type", "precedence"]],
                 hide_index=True, width="stretch")
    c2.markdown("**What the agent will remember**")
    case = storage.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
    c2.dataframe(pd.DataFrame(storage.recall(case["charterers"], case["port"], case["vessel"])),
                 hide_index=True, width="stretch")
    st.stop()

run = service.get_run(run_id)
state = service.get_state(run_id)
calc = state.get("calc") or {}

# ------------------------------------------------------------------ approval checkpoint
if run["status"] == "awaiting_approval":
    st.warning("⏸ The agent paused for human approval before drafting the claim. Review the statement below.")
    with st.form("approve"):
        who = st.text_input("Your name", value="Claims manager")
        note = st.text_input("Note (optional)")
        a, b = st.columns(2)
        ok = a.form_submit_button("✅ Approve & draft letter", type="primary")
        rej = b.form_submit_button("❌ Reject")
    if ok or rej:
        with st.spinner("Resuming from checkpoint..."):
            service.decide(run_id, approved=bool(ok), approver=who, note=note)
        st.rerun()

# ------------------------------------------------------------------ headline
def short(ts):
    try:
        return pd.to_datetime(ts).strftime("%d %b %H:%M")
    except Exception:
        return ts or "-"


st.caption(f"Run `{run_id}` · status **{run['status'].replace('_', ' ')}** · LLM `{run['provider']}`")
m = st.columns(4)
m[0].metric("Result", calc.get("result", "-"))
m[1].metric("Amount (USD)", f"{calc.get('amount_usd', 0):,.2f}" if calc else "-")
m[2].metric("Laytime commenced", short(calc.get("laytime_commenced")))
tb = calc.get("time_bar") or {}
m[3].metric(f"Time bar ({tb.get('deadline', '-')})", f"{tb.get('days_left')} days left" if tb else "-",
            help=f"Claim must be presented within {tb.get('days')} days of completion ({tb.get('clause')})")
if tb.get("status") in ("URGENT", "EXPIRED"):
    st.error(f"Time bar {tb['status']}: deadline {tb['deadline']} ({tb['days_left']} days left)")

tabs = st.tabs(["Agent trace", "Laytime statement", "Terms & sources", "Evidence", "Claim letter", "Memory"])

with tabs[0]:
    loops = [t for t in run["trace"] if t["kind"] == "loop"]
    st.caption(f"{len(run['trace'])} steps · {len(loops)} self-correction loop events · LLM: {run['provider']}")
    for e in run["trace"]:
        if e["data"] in (None, [], {}):
            st.markdown(line(e))
        else:
            with st.expander(line(e)):
                st.json(e["data"], expanded=False)

with tabs[1]:
    if calc:
        st.markdown(f"**Allowance:** {calc.get('allowance_basis')} · **Commenced:** {calc['laytime_commenced']} "
                    f"({state['commencement']['how']}) · **Expired:** {calc.get('laytime_expired') or '-'} · "
                    f"**Completed:** {calc['completed']}")
        df = pd.DataFrame(calc["deductions"])
        if not df.empty:
            st.markdown("**Deductions (time not counting)**")
            st.dataframe(df[["start", "end", "reason", "hours_applied", "applies_on_demurrage", "clause_ref",
                             "evidence", "status"]], hide_index=True, width="stretch")
        if state.get("counted_periods"):
            st.markdown("**Stoppages examined that COUNT as laytime**")
            st.dataframe(pd.DataFrame(state["counted_periods"]).astype(str), hide_index=True, width="stretch")
    for c in state.get("corrections", []):
        st.success(f"✏️ Corrected {c['what']}: {c['from']} → {c['to']} (evidence: {c['evidence']})")
    for f in state.get("findings", []):
        (st.error if f["severity"] in ("high", "error") else st.info)(f["text"])

with tabs[2]:
    rows = []
    for t, v in (state.get("terms") or {}).items():
        for f, val in v["value"].items():
            rows.append({"term": v["label"], "field": f, "value": json.dumps(val) if isinstance(val, (dict, list)) else str(val),
                         "source": v["field_sources"].get(f)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ov = [{k: str(x) for k, x in (o | {"term": t}).items()} for t, v in (state.get("terms") or {}).items()
          for o in v.get("overrides", [])]
    if ov:
        st.markdown("**Precedence decisions (recap / rider over printed C/P)**")
        st.dataframe(pd.DataFrame(ov), hide_index=True, width="stretch")
    if state.get("unresolved"):
        st.error(f"Unresolved terms: {state['unresolved']}")

with tabs[3]:
    st.markdown("**Notices of Readiness**")
    for n in state.get("nors", []):
        ok = (state.get("valid_nor") or {}).get("number") == n["number"]
        st.markdown(f"{'✅' if ok else '❌'} NOR No. {n['number']} - {n['tendered']} - {n['position']}")
    imgs = [d for d in state.get("docs", []) if d["doc_type"] == "image"]
    if imgs:
        st.markdown("**Image evidence**")
        cols = st.columns(len(imgs))
        for c, d in zip(cols, imgs):
            c.image(str(config.ROOT / d["path"]), caption=d["filename"], width="stretch")
            reading = next((i for i in state.get("images", []) if i.get("file") == d["filename"]), None)
            if reading:
                c.caption(reading.get("summary", ""))
    for r in state.get("reread_results", []):
        with st.expander(f"Loop B re-read: {r['request']['type']} - {r['request'].get('why', '')}"):
            st.json(r["sources"])

with tabs[4]:
    if state.get("letter"):
        st.markdown(state["letter"])
        st.download_button("Download claim letter (.md)", state["letter"], file_name=f"claim_letter_{run_id}.md")
        out_dir = config.ROOT / state["outputs"]["dir"]
        st.download_button("Download laytime statement (.csv)", (out_dir / "laytime_statement.csv").read_bytes(),
                           file_name=f"laytime_statement_{run_id}.csv")
    else:
        st.info("The letter is drafted after approval.")

with tabs[5]:
    st.markdown("**Recalled at the start of this run**")
    st.dataframe(pd.DataFrame(state.get("memory", [])), hide_index=True, width="stretch")
    st.markdown("**All learned lessons**")
    st.dataframe(pd.DataFrame(storage.rows("SELECT created_at, port, counterparty, text, source_run FROM lessons "
                                           "ORDER BY id DESC")), hide_index=True, width="stretch")
