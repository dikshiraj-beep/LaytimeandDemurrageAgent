# Laytime & Demurrage Claim Agent

An agentic AI that prepares laytime / demurrage claims for a shipping company. It reads the charter party,
fixture recap, negotiation emails, Notices of Readiness, Statement of Facts, weather logs and image evidence,
then **plans, retrieves, grades, validates, self-corrects, calculates, verifies, pauses for human approval**
and drafts a cited claim letter. It remembers lessons from past claims.

> All data in `data/` is **synthetic** (fictional vessels, companies and ports). Safe for demos and public repos.

![Architecture](docs/architecture.png)

![The app paused at the approval checkpoint on Case C](docs/ui_screenshot.png)

| Layer | What it is | Where |
|---|---|---|
| UI | Streamlit web app (live agent trace, approval checkpoint, letter download) | `ui/app.py` |
| REST API | FastAPI (`/runs`, `/runs/{id}/decision`, `/runs/{id}/letter` ...) | `laytime_agent/api.py` |
| Agent loop | LangGraph state machine with 3 self-correction loops + human-in-the-loop | `laytime_agent/agent/` |
| LLM | Anthropic Claude, OpenAI or Azure OpenAI (or `mock` = offline heuristics) | `laytime_agent/llm.py` |
| Tools | SOF/NOR readers, clause grader, weather, holidays, port-limit geo check, vision, laytime calculator | `laytime_agent/tools/` |
| Retrieval | Chroma vector DB + BM25, fused with reciprocal rank fusion | `laytime_agent/vectorstore.py` |
| Storage + memory | SQLite by default or optional PostgreSQL: documents, chunks, weather, holidays, ports, past claims, lessons, runs, trace, and LangGraph checkpoints | `laytime_agent/storage.py`, `storage/` |
| Evaluation | Scores the agent and a naive one-shot RAG baseline against the answer key | `evals/` |

---

## Quick start (about 10 minutes)

**Requirements:** Python 3.11 or 3.12 (recommended), VS Code with the Python extension, internet for `pip install`.

### 1. Open the folder in VS Code
`File > Open Folder...` and pick this project folder.

### 2. Set up (one command)
Open a terminal in VS Code (`Terminal > New Terminal`) and run:

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```
**macOS / Linux**
```bash
bash scripts/setup_mac_linux.sh
```
This creates `.venv`, installs `requirements.txt`, creates `.env` (mock mode), and ingests the data into
SQLite + the Chroma vector DB. You can also run it from `Terminal > Run Task... > Setup`.

Then select the interpreter: `Ctrl+Shift+P > Python: Select Interpreter > .venv`.

### Optional: use PostgreSQL for relational records
The default is local SQLite. To use your PostgreSQL server, install the requirements, then set `DATABASE_URL`
in your ignored local `.env` (never commit or share it):
```ini
DATABASE_URL=postgresql://laytime_app:URL_ENCODED_PASSWORD@127.0.0.1:5432/laytime_agent
```
URL-encode special characters in the password. Restart the app after changing `.env`. PostgreSQL then stores
case metadata, document text/chunks, weather and shared reference records, lessons, runs, traces, and new
LangGraph approval checkpoints. Run `python run.py migrate-db` once to copy those existing relational records
from `storage/laytime.db`; the command refuses a non-empty PostgreSQL target and keeps the SQLite source intact.

Original uploaded files remain under `data/cases/`, generated letters/statements remain under `outputs/`, and
the Chroma vector index remains under `storage/chroma/`. These file/vector stores are still local and are not
made central by the PostgreSQL setting.

### 3. Run
Use the **Run and Debug** panel (`Ctrl+Shift+D`) and pick a configuration:

| Launch configuration | What it does |
|---|---|
| 0. Setup check | Shows Python, LLM provider, embeddings, cases; pings the LLM |
| 1. Ingest data | Rebuilds the database and vector index from `data/` |
| **2. UI (Streamlit)** | Opens the app at http://localhost:8501 |
| 3. REST API (FastAPI) | API + Swagger docs at http://127.0.0.1:8000/docs |
| 4. Run Case C in terminal | Full agent run in the terminal, asks you to approve |
| 5. Evaluate agent vs answer key | Agent vs naive RAG scorecard -> `evals/report.md` |
| 6. Tests (pytest) | Unit, end-to-end and LLM-path tests |
| UI + API together | Starts both |

Or from the terminal (with `.venv` active):
```bash
python run.py ui                    # web app
python run.py api                   # REST API
python run.py case case_C_seren_talon
python run.py eval
python -m pytest -q
```

### 4. Connect a real LLM
Edit `.env`:
```ini
LLM_PROVIDER=anthropic          # or openai / azure
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5-5
```
Run `python run.py check` - it pings the model. Restart the UI. The agent now uses the LLM for planning,
clause grading/extraction, query rewriting, reading images (AIS screenshot, signed SOF scan, deck log),
letter polishing and writing memory lessons. Arithmetic always stays in deterministic code.

---

## Using the app

1. Pick a case in the sidebar (A easy, B medium, C hard) and click **Run agent**. Watch the live trace.
2. The agent pauses at the **human approval checkpoint**. Review the *Laytime statement*, *Terms & sources*
   and *Evidence* tabs, then **Approve** (or Reject).
3. The *Claim letter* tab shows the cited letter; download it with the laytime statement CSV.
4. The *Memory* tab shows what was recalled at the start and the lesson saved at the end.

Expected results: Case A demurrage USD 27,825.00 · Case B despatch USD 5,958.33 · Case C demurrage USD 32,290.10.

## REST API examples
```bash
curl -X POST localhost:8000/runs -H "Content-Type: application/json" -d '{"case_id":"case_C_seren_talon"}'
curl localhost:8000/runs/<run_id>
curl -X POST localhost:8000/runs/<run_id>/decision -H "Content-Type: application/json" -d '{"approved":true,"approver":"me"}'
curl localhost:8000/runs/<run_id>/letter
```

## Project structure
```
laytime-agent/
├─ run.py                     # single entry point (check / ingest / ui / api / case / eval / graph)
├─ requirements.txt  .env.example  pytest.ini
├─ laytime_agent/
│  ├─ config.py  llm.py  storage.py  vectorstore.py  ingest.py  service.py  api.py
│  ├─ agent/   state.py  nodes.py  graph.py
│  └─ tools/   documents.py  terms.py  evidence.py  laytime.py
├─ ui/app.py                  # Streamlit front end
├─ data/cases/<case>/         # C/P, recap, emails, NOR(s), SOF, weather log, images
├─ data/shared/               # holidays, port info, company terms, past claims, letter template
├─ evals/                     # answer key (hidden from the agent), baseline, scorer
├─ tests/                     # unit, end-to-end, LLM-path tests
├─ docs/                      # architecture diagram + notes
├─ storage/                   # created at runtime: laytime.db, chroma/, checkpoints.db
└─ outputs/<run_id>/          # claim_letter.md, laytime_statement.json/.csv
```

## Adding your own case
Create `data/cases/<new_case>/` with a `charter_party.pdf`, `statement_of_facts.pdf`, NOR PDF(s), optional
`fixture_recap_email.pdf`, `port_weather_log.csv` and images, then click **Ingest / rebuild index**.
Add the port to `data/shared/port_information.json` and its holidays to `port_holidays_2026.csv`.
(The SOF/NOR readers expect table layouts like the samples; real-world layouts may need the LLM extractor - see PLAN.md.)

## Troubleshooting
| Problem | Fix |
|---|---|
| `Default embedding model unavailable` (corporate proxy blocks the model download) | It falls back automatically; or set `EMBEDDINGS=hash` (offline) or `EMBEDDINGS=openai` |
| `pip install chromadb` fails | Use Python 3.11/3.12; upgrade pip; on Windows install "Microsoft C++ Build Tools" if asked |
| LLM ping FAILED | Check the API key, model name and `LLM_PROVIDER` in `.env`; behind a proxy set `HTTPS_PROXY` |
| Port 8501/8000 already in use | Stop the other process or add `--server.port 8502` / `--port 8001` |
| Odd results after changing data | Run `python run.py ingest --reset` |
| Start completely fresh | Delete the `storage/` and `outputs/` folders, then ingest again |

Never commit `.env` (it is in `.gitignore`).
