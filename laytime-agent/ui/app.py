"""Streamlit front end.   Run:  python run.py ui   ->  http://localhost:8501"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from laytime_agent import config, ingest, service, storage, uploads  # noqa: E402
from laytime_agent.llm import get_llm  # noqa: E402

st.set_page_config(page_title="Laytime & Demurrage Agent", page_icon="⚓", layout="wide")

st.markdown("""
<style>
:root {
    --laytime-navy: #17324d;
    --laytime-navy-deep: #10263c;
    --laytime-orange: #e77b24;
    --laytime-grey: #eef1f4;
    --laytime-grey-border: #d3d9df;
    --laytime-ink: #243746;
}

[data-testid="stAppViewContainer"] {
    background: var(--laytime-grey);
    color: var(--laytime-ink);
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: var(--laytime-navy);
    border-right: 4px solid var(--laytime-orange);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #f7f9fb;
}

[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #d6e0e8;
}

[data-testid="stSidebar"] hr {
    border-color: #718398;
}

[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] button[kind="secondary"] {
    border-color: var(--laytime-orange);
    background: var(--laytime-orange);
    color: #ffffff;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #ffffff;
    color: var(--laytime-ink);
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid #718398;
    border-left: 4px solid var(--laytime-orange);
    border-radius: 6px;
    background: var(--laytime-navy-deep);
}

[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3 {
    color: var(--laytime-navy);
}

[data-testid="stMain"] h1 {
    padding-bottom: 0.45rem;
    border-bottom: 4px solid var(--laytime-orange);
}

[data-testid="stMain"] [data-testid="stCaptionContainer"] {
    color: #5d6b76;
}

[data-testid="stTabs"] [role="tablist"] {
    align-items: flex-end;
    gap: 0.55rem;
    padding: 0.35rem 0.4rem 0;
    border-bottom: 3px solid var(--laytime-navy);
    background: #e2e6eb;
}

[data-testid="stTabs"] [role="tab"] {
    min-height: 3.25rem;
    margin: 0;
    padding: 0.78rem 1.1rem 0.72rem;
    color: #344b5f;
    background: #d4dbe2;
    border: 1px solid #aeb9c4;
    border-bottom: 0;
    border-radius: 9px 9px 0 0;
    font-size: 1rem;
    font-weight: 650;
    opacity: 1;
    transition: background-color 120ms ease, color 120ms ease, transform 120ms ease;
}

[data-testid="stTabs"] [role="tab"]:hover:not([aria-selected="true"]) {
    color: var(--laytime-navy-deep);
    background: #c3cdd6;
    transform: translateY(-2px);
}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #ffffff;
    background: var(--laytime-navy);
    border: 1px solid var(--laytime-orange);
    border-bottom: 0;
    box-shadow: inset 0 5px 0 var(--laytime-orange);
    font-weight: 750;
}

[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    margin-top: 0;
    padding: 1.25rem;
    border: 1px solid var(--laytime-grey-border);
    border-top: 0;
    border-radius: 0 0 8px 8px;
    background: #ffffff;
}

[data-testid="stMetric"] {
    min-height: 112px;
    padding: 0.85rem 1rem;
    border: 1px solid var(--laytime-grey-border);
    border-top: 4px solid var(--laytime-orange);
    border-radius: 6px;
    background: #ffffff;
}

[data-testid="stMetricLabel"] {
    color: #566777;
}

[data-testid="stMetricValue"] {
    color: var(--laytime-navy);
}

[data-testid="stMain"] [data-testid="stSelectbox"] label {
    color: var(--laytime-navy);
    font-weight: 700;
}

[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    min-height: 48px;
    border: 2px solid var(--laytime-orange);
    border-radius: 6px;
    background: #ffffff;
}

[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] svg {
    color: var(--laytime-navy);
}

[data-testid="stExpander"] {
    border: 1px solid var(--laytime-grey-border);
    border-left: 4px solid var(--laytime-orange);
    border-radius: 6px;
    background: #ffffff;
}

[data-testid="stFileUploader"] section {
    border: 2px dashed var(--laytime-orange);
    border-radius: 6px;
    background: #f5f6f8;
}

[data-testid="stMain"] button[kind="primary"] {
    border-color: var(--laytime-orange);
    background: var(--laytime-orange);
    color: #ffffff;
}

[data-testid="stMain"] button[kind="primary"]:hover,
[data-testid="stSidebar"] button:hover {
    border-color: #c96312;
    background: #c96312;
    color: #ffffff;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--laytime-grey-border);
    border-radius: 6px;
    background: #ffffff;
}
</style>
""", unsafe_allow_html=True)

ICON = {"plan": "🧭", "memory": "🧠", "tool": "🔧", "llm": "✨", "vision": "👁️", "grade": "⚖️", "resolved": "✅",
        "precedence": "📑", "loop": "🔁", "finding": "🚩", "correction": "✏️", "warning": "⚠️", "error": "⛔",
        "verify": "🔍", "approval": "🙋", "output": "📄", "info": "ℹ️"}
NODE_LABEL = {"plan": "1 Plan", "extract": "2 Extract", "retrieve": "3 Retrieve", "grade": "4 Grade",
              "validate": "5 Validate", "calculate": "6 Calculate", "verify": "6 Verify", "approval": "Approval",
              "draft": "Draft + memory"}


def line(e):
    return f"{ICON.get(e['kind'], '•')} **{NODE_LABEL.get(e['node'], e['node'])}** · {e['message']}"


def go_to_page(page: str, open_upload: bool = False):
    st.session_state["page"] = page
    if open_upload:
        st.session_state["open_case_upload"] = True
        st.session_state.pop("run_id", None)


def start_existing_claim():
    st.session_state.pop("run_id", None)
    st.session_state["page"] = "Claims workspace"


def open_run(run_id: str):
    st.session_state["run_id"] = run_id
    st.session_state["page"] = "Claims workspace"


# ------------------------------------------------------------------ sidebar
storage.init_db()
st.session_state.setdefault("page", "Home")
with st.sidebar:
    st.title("⚓ Laytime agent")
    st.caption(f"LLM: `{get_llm().label}`")
    if not get_llm().available:
        st.info("Mock mode: deterministic heuristics replace the LLM. Set LLM_PROVIDER and an API key in `.env` "
                "for grading, vision and drafting by a real model.")
    st.divider()
    st.caption("NAVIGATION")
    nav_left, nav_right = st.columns(2)
    nav_left.button("Home", width="stretch", on_click=go_to_page, args=("Home",), key="nav_home")
    nav_right.button("Claims", width="stretch", on_click=go_to_page, args=("Claims workspace",), key="nav_claims")
    st.button("Previous runs", width="stretch", on_click=go_to_page, args=("Previous runs",), key="nav_runs")
    st.button("Calculation references", width="stretch", on_click=go_to_page,
              args=("Calculation references",), key="nav_calculation_references")

page = st.session_state["page"]
if page == "Home":
    st.markdown("### CLAIMS OPERATIONS")
    st.title("Laytime & Demurrage Claim Agent")
    st.markdown("#### Welcome")
    st.write("Prepare a reviewable laytime statement and cited draft claim from voyage documents. The agent checks source documents, terms and operational evidence, then pauses for your decision before drafting.")

    action_new, action_existing = st.columns(2, gap="large")
    with action_new:
        with st.container(border=True):
            st.markdown("#### Upload a new case")
            st.write("Add the charter party, Statement of Facts and NOR documents. Weather records and image evidence can also be included.")
            st.button("Upload new case", type="primary", width="stretch", on_click=go_to_page,
                      args=("Claims workspace", True), key="home_upload")
    with action_existing:
        with st.container(border=True):
            st.markdown("#### Run an existing claim")
            st.write("Choose one of the indexed cases, run the agent, and review its evidence and calculation before approval.")
            st.button("Open claims workspace", width="stretch", on_click=start_existing_claim,
                      key="home_existing")

    st.subheader("How a claim moves through the app")
    step_cols = st.columns(4)
    steps = [
        ("01  Documents", "Upload a case or choose an indexed one."),
        ("02  Analysis", "Review extracted facts, contract terms and evidence."),
        ("03  Calculation", "Inspect laytime, deductions, citations and verification."),
        ("04  Decision", "Approve to draft the letter, or reject the run."),
    ]
    for column, (title, description) in zip(step_cols, steps):
        with column:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(description)

    st.button("View calculation formulas", icon=":material/functions:", on_click=go_to_page,
              args=("Calculation references",), key="home_calculation_references")

    st.info("The current demo uses fictional sample data and local storage. A human reviewer remains responsible for the claim decision.")
    st.stop()

if page == "Calculation references":
    st.markdown("### CLAIMS OPERATIONS")
    st.title("Calculation references", icon=":material/functions:")
    st.write("These are the deterministic rules used by Step 03, **Calculation**. The agent identifies relevant periods and contract terms; Python code performs the time and money arithmetic.")
    st.badge("Deterministic calculation", icon=":material/calculate:", color="orange")

    with st.container(border=True):
        st.subheader("1. Time counted against the laytime allowance")
        st.write("The calculator walks from valid laytime commencement to completion in one-minute increments. Excluded intervals pause the clock according to their contractual treatment.")
        st.latex(r"L_{used} = \sum_{m=t_0}^{t_c-1} I(m \text{ counts as laytime}) \;\text{minutes}")
        st.latex(r"L_{allowed,minutes} = \operatorname{round}(L_{allowed,hours} \times 60)")
        st.caption("An exclusion pauses the clock before expiry. Once allowance is consumed, it pauses demurrage time only when its applies_on_demurrage flag is true.")

    with st.container(border=True):
        st.subheader("2. Laytime expiry and demurrage")
        st.write("Laytime expires at the end of the minute that consumes the allowance. Countable time after that point is time on demurrage.")
        st.latex(r"D_{days} = \frac{D_{minutes}}{1{,}440}")
        st.latex(r"\text{Demurrage amount} = \operatorname{round}(D_{days} \times R_{demurrage/day}, 2)")
        st.caption("The calculator returns DEMURRAGE when any demurrage minutes accrue; the final amount is rounded to two decimal places in the case currency (USD in this app).")

    with st.container(border=True):
        st.subheader("3. Despatch")
        st.write("When no demurrage time accrues, unused allowance is valued at the configured despatch fraction of the demurrage rate.")
        st.latex(r"L_{saved,hours} = L_{allowed,hours} - L_{used,hours}")
        st.latex(r"R_{despatch/day} = R_{demurrage/day} \times f_{despatch}")
        st.latex(r"\text{Despatch amount} = \operatorname{round}\!\left(\frac{L_{saved,hours}}{24} \times R_{despatch/day}, 2\right)")
        st.caption("The default despatch fraction is 0.5, but the value is passed into the calculator and can be set by case terms.")

    with st.container(border=True):
        st.subheader("4. Independent verification")
        st.write("A second verifier uses merged time intervals rather than the calculator's minute-by-minute loop. It checks result type, laytime/demurrage duration, amount consistency, chronological exclusions, and required clause/evidence citations.")
        st.latex(r"\text{Amount check: }\quad A = \operatorname{round}(D_{days} \times R_{demurrage/day}, 2)")
        st.caption("Implementation: laytime_agent/tools/laytime.py (calculate and verify). The independent verifier is also defined there.")

    st.warning("These formulas explain the software behavior; the applicable charter party, recap, riders and approved evidence determine which periods and rates are used. Review the statement before approving a claim.")
    st.button("Back to claims workspace", icon=":material/arrow_back:", on_click=go_to_page,
              args=("Claims workspace",), key="calculation_reference_back")
    st.stop()

if page == "Previous runs":
    st.markdown("### CLAIMS OPERATIONS")
    st.title("Previous runs")
    all_runs = storage.rows(
        "SELECT run_id, case_id, started_at, finished_at, status, provider, approved_by "
        "FROM runs ORDER BY started_at ASC, run_id ASC"
    )
    serial_by_run = {item["run_id"]: f"PR-{number:03d}" for number, item in enumerate(all_runs, start=1)}
    history = list(reversed(all_runs))
    if not history:
        st.info("No agent runs have been recorded yet.")
        st.button("Go to claims workspace", on_click=go_to_page, args=("Claims workspace",), type="primary")
        st.stop()

    history_rows = []
    for item in history:
        result = storage.get_run(item["run_id"]).get("result") or {}
        history_rows.append({
            "Run #": serial_by_run[item["run_id"]],
            "Run": item["run_id"],
            "Case": item["case_id"],
            "Status": item["status"].replace("_", " "),
            "Result": result.get("result", "-"),
            "Amount (USD)": result.get("amount_usd"),
            "Provider": item["provider"],
            "Started": item["started_at"],
        })
    st.dataframe(pd.DataFrame(history_rows), hide_index=True, width="stretch")
    run_options = {item["run_id"]: f"{serial_by_run[item['run_id']]} | {item['case_id']} | "
                                      f"{item['status'].replace('_', ' ')} | {item['run_id']}"
                   for item in history}
    with st.container(border=True):
        st.header("Open a run", icon=":material/folder_open:")
        st.badge("Choose a run to inspect its trace and claim output", color="orange")
        selected_run = st.selectbox("Select previous run", list(run_options), format_func=run_options.get,
                                   key="selected_previous_run")
        st.button("Open selected run", type="primary", icon=":material/open_in_new:",
                  on_click=open_run, args=(selected_run,))
    st.stop()

st.markdown("### CLAIM WORKSPACE")
st.title("Run and review a claim")
st.caption("Plan → Extract → Retrieve → Grade → Validate → Calculate/Verify → Human approval → Claim letter")

with st.sidebar:
    cases = storage.list_cases()
    if ingest.sources_changed():
        st.warning("Case or shared source files changed since the last index build.")
        if st.button("Rebuild index", type="primary", width="stretch"):
            with st.spinner("Reading documents, chunking clauses, building vector index..."):
                stats = ingest.ingest(reset=True)
            st.success(f"{stats['documents']} documents, {stats['chunks']} chunks ({stats['embeddings']} embeddings)")
            cases = storage.list_cases()
    with st.expander("Upload case documents", expanded=st.session_state.get("open_case_upload", False)):
        upload_mode = st.radio("Upload to", ["New case", "Existing case"], horizontal=True, key="upload_mode")
        create_case = upload_mode == "New case"
        if create_case:
            upload_case_id = st.text_input("New case ID", placeholder="claim_001", key="upload_case_id").strip()
        elif cases:
            upload_labels = {
                c["case_id"]: f"{c.get('vessel') or c['case_id']} - {c.get('operation') or 'operation'} at {c.get('port') or 'port'}"
                for c in cases
            }
            upload_case_id = st.selectbox("Case", list(upload_labels), format_func=upload_labels.get,
                                          key="upload_existing_case")
        else:
            upload_case_id = ""
            st.info("Create a new case first; no existing cases are available.")
        uploaded_files = st.file_uploader(
            "Select case documents",
            type=["pdf", "csv", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            help="New cases need a charter party PDF, Statement of Facts PDF, and at least one NOR PDF. Weather CSVs and image evidence are optional.",
            key="case_documents_upload",
        )
        st.caption("Each file is limited to 50 MB. Files are added to the selected case and indexed locally.")
        if st.button("Upload and index documents", type="primary", disabled=not upload_case_id):
            try:
                result = uploads.stage_case_uploads(
                    config.CASES_DIR,
                    upload_case_id,
                    [(item.name, item.getvalue()) for item in uploaded_files or []],
                    create_case=create_case,
                )
                with st.spinner("Indexing case documents..."):
                    stats = ingest.ingest(reset=True)
                st.session_state["upload_notice"] = (
                    f"Uploaded {result['files']} files. Indexed {stats['documents']} documents across "
                    f"{stats['cases']} cases."
                )
                st.session_state.pop("run_id", None)
                st.session_state["open_case_upload"] = False
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Upload or indexing failed: {exc}")
    if notice := st.session_state.pop("upload_notice", None):
        st.success(notice)
    if not cases:
        st.warning("No cases loaded yet - ingest or upload documents first.")
        st.stop()
    labels = {c["case_id"]: f"{c['vessel']} - {c['operation']} at {c['port']}" for c in cases}
    case_id = st.selectbox("Claim case", list(labels), format_func=lambda k: labels[k])
    auto = st.checkbox("Auto-approve (skip human checkpoint)", value=False)
    run_clicked = st.button("▶ Run agent", type="primary", width="stretch")

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
