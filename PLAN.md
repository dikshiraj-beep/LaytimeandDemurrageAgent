# Project Plan - Laytime & Demurrage Claim Agent

## 1. Goal and success criteria

**Goal:** an AI agent that turns a voyage's documents into a correct, cited laytime statement and claim letter,
and goes clearly beyond one-shot RAG (embed -> search -> answer).

| Challenge requirement | How this project meets it | Where in the code |
|---|---|---|
| Autonomous planning | Planner builds a case-specific checklist from the documents found and lessons in memory | `agent/nodes.py: plan()` |
| Multi-step tool execution | SOF/NOR readers, hybrid clause search, weather log, holiday calendar, port-limit geo check, vision, laytime calculator, letter writer | `tools/`, `vectorstore.py` |
| Retrieval grading | Every retrieved clause is graded (binding? right operation? actually states the term?) and recap/rider precedence is applied field by field | `agent/nodes.py: grade()`, `tools/terms.py` |
| Self-correction | Loop A (rewrite query), Loop B (re-read independent sources on evidence conflicts), Loop C (independent verifier routes back) | `graph.py`, `nodes.py` |
| Persistent memory | Past claims + learned lessons in SQLite, recalled by counterparty / port / vessel, written after approval; LangGraph checkpoints persist paused runs | `storage.py`, `nodes.py: draft()` |
| Human in the loop | Run pauses before the claim letter; approve/reject in UI, API or CLI; resumes from checkpoint | `nodes.py: approval()`, `service.py` |

**Success criteria (measured by `python run.py eval`):**
- Agent passes 16/16 answer-key checks on Cases A-C (result type, amount ±USD 1, commencement, time bar, deductions, valid NOR).
- Naive RAG baseline scores clearly lower (currently 5/16) - the "why an agent" evidence.
- Every deduction in the letter cites a clause and an evidence line.

---

## 2. Current status

| Component | Status |
|---|---|
| Synthetic data pack (3 cases, images, answer key) | Done |
| Ingestion -> SQLite + Chroma (clause-aware chunks) | Done |
| Hybrid retrieval (dense + BM25 + RRF) | Done |
| Agent graph with loops A/B/C + approval checkpoint | Done |
| Deterministic laytime engine + independent verifier | Done |
| LLM providers: Anthropic / OpenAI / Azure / mock | Done (mock and stand-in tested; test your real key with `run.py check` and `run.py eval`) |
| Streamlit UI, FastAPI, CLI | Done |
| Evaluation vs answer key + naive baseline | Done (mock: agent 16/16, baseline 5/16) |
| Tests (unit, end-to-end, LLM path) | Done (12 tests) |

---

## 3. Step-by-step plan

### Phase 0 - Set up (Day 1, ~1 hour)
1. Install Python 3.11/3.12 and VS Code (+ Python extension).
2. Open the project folder in VS Code.
3. Run the setup task (`Terminal > Run Task... > Setup (Windows)` or the script in README).
4. Select the `.venv` interpreter.
5. Run **0. Setup check**, then **6. Tests** - all green.
6. `git init`, commit, push to your repo (`.env`, `storage/`, `outputs/` are git-ignored).

**Done when:** tests pass and `run.py check` shows 3 cases.

### Phase 1 - Run it offline and understand the flow (Day 1-2)
1. Launch **2. UI (Streamlit)**; run Case A, then B, then C (mock mode).
2. For each run, read the *Agent trace* tab top to bottom and match each step to the diagram in `docs/architecture.png`.
3. Run **4. Run Case C in terminal** and approve at the prompt.
4. Run **5. Evaluate** and open `evals/report.md`.
5. Read `docs/ARCHITECTURE.md` and skim `agent/nodes.py` node by node.

**Done when:** you can explain what each loop does, and the three conflicts loop B resolves in Case C
(invalid NOR No. 1, SOF date typo, disputed rain).

### Phase 2 - Connect the real LLM (Day 2)
1. Get an API key (Anthropic, OpenAI, or your company's Azure OpenAI deployment).
2. Set `LLM_PROVIDER`, the key and the model in `.env`. Keep `EMBEDDINGS=default` (or `openai`).
3. `python run.py check` -> "LLM ping: 'OK'".
4. `python run.py ingest --reset` (rebuilds the vector index with real embeddings).
5. Run Case C in the UI. In the trace you should now see: *Checklist refined by the LLM*, `✨`/`👁️` vision
   steps reading the AIS screenshot, the signed SOF scan and the deck log, and the AIS coordinates confirming
   NOR No. 1 was ~14 nm out.
6. `python run.py eval` - target 16/16 again. If a check fails, open the trace of that run and look for
   `llm_vs_rules_disagreement` entries in the *grade* steps.

**Done when:** eval passes with the real model and vision evidence appears in Case C.

### Phase 3 - Harden and tune (Day 3-4)
1. **Prompts:** tune the grader prompt in `tools/terms.py: grade_and_extract()` and the vision prompt in
   `tools/evidence.py: VISION_PROMPT` until the trace shows clean decisions.
2. **Retrieval:** compare `EMBEDDINGS=default` vs `openai`; adjust `RETRIEVAL_TOP_K`.
3. **Edge cases to try** (copy a case folder and edit the CSV/PDF text generator in the sample pack):
   NOR tendered outside office hours (Case A window 06:00-18:00); a strike after laytime expiry; a vessel-gear
   breakdown; a missing recap. Check the agent reacts correctly.
4. Add a unit test for every bug you fix (`tests/`).

### Phase 4 - Evaluation evidence (Day 4-5)
1. Run `python run.py eval` in mock mode and with the real LLM; keep both reports.
2. Make a small table for the submission: agent vs naive RAG, per case and per check.
3. Optional: time how long a human takes for Case C vs the agent.

### Phase 5 - Demo and polish (Day 5-6)
1. Set `AS_OF_DATE=2026-10-01` in `.env` so the time-bar warning is repeatable.
2. Rehearse the 3-minute demo (section 4).
3. Screenshots: trace with loops, precedence table, evidence tab with images, approval, letter.

### Phase 6 - Submission (Day 7)
1. README up to date, architecture diagram, eval report, short video/GIF of the Case C run.
2. Push to GitHub; check a fresh clone works by following README only.

### Phase 7 - Path to production (after the challenge)
1. **Real documents:** add an LLM-based extractor for SOF/NOR layouts that are not tables (the hook is
   `tools/documents.py`); add OCR for scanned PDFs.
2. **Company data:** replace `data/shared` with your port database, holiday calendars and claims history
   (SQLite tables are already in place - or point `storage.py` at Postgres).
3. **Security:** run inside your Azure tenant (Azure OpenAI + Azure AI Search as the vector store), SSO in front
   of the UI, keep the audit trail (`trace` table).
4. **Microsoft 365:** expose `laytime_agent/api.py` as a custom connector / MCP tool for Copilot Studio so users
   can trigger claims from Teams while the agent logic stays in this code base.
5. **More terms:** rider clauses, reversible laytime, half-rate demurrage for weather, port-specific customs.

---

## 4. Three-minute demo script (Case C)

| Time | Show | Say |
|---|---|---|
| 0:00 | Sidebar, case documents | "A demurrage claim needs the C/P, recap, emails, NORs, SOF, weather and photos. Analysts spend hours cross-reading them." |
| 0:20 | Click Run, live trace | "The agent plans first - note the lesson it pulled from memory about Santa Rilla NORs." |
| 0:45 | Grade + precedence lines | "It rejects the loading clause and the negotiation emails, and applies the recap over the printed C/P: USD 14,250 not 15,000; 120-day time bar not 90." |
| 1:15 | Loop B lines, Evidence tab | "Three conflicts. NOR No. 1 was 14 nm out - confirmed from the AIS screenshot - so laytime runs from NOR No. 2. The SOF says rain stopped before it started - corrected from the weather log and the signed scan. The rain stoppage the port agent recorded on 16 June is rejected - weather log, deck log and Master's protest all say dry." |
| 2:00 | Verify PASSED, time-bar warning | "An independent calculator re-checks the numbers and every citation. Only 16 days left on the time bar." |
| 2:20 | Approve, letter | "A human approves; the agent drafts the cited claim and saves a lesson for next time." |
| 2:45 | `evals/report.md` | "Against the answer key the agent scores 16/16; one-shot RAG scores 5/16." |

---

## 5. Risks and mitigations

| Risk | Mitigation already in the design |
|---|---|
| LLM hallucinates a number | Arithmetic is deterministic code; LLM values are cross-checked with rule extraction; letter polish is rejected if any figure changes |
| Wrong clause retrieved | Grader + query rewrite (loop A) + precedence check against recap/rider |
| Bad source data (typos, disputes) | Loop B requires a second, independent source before correcting or rejecting |
| Silent calculation error | Loop C: interval-arithmetic verifier independent of the minute engine |
| Claim submitted late | Time-bar deadline and days-left check, warning in UI and letter |
| Unreviewed output leaves the company | Mandatory approval checkpoint before drafting |
| No API key / blocked network | `mock` LLM mode and `hash` embeddings run fully offline |
