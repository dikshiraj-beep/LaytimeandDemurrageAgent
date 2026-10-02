"""One entry point for everything.

  python run.py check              # verify setup (packages, .env, data)
    python run.py ingest [--reset]   # load documents -> configured DB + Chroma vector DB
    python run.py migrate-db         # copy local SQLite records to an empty configured PostgreSQL DB
  python run.py ui                 # Streamlit front end  (http://localhost:8501)
  python run.py api                # FastAPI REST API      (http://127.0.0.1:8000/docs)
  python run.py case <case_id> [--auto]   # run one case in the terminal
  python run.py eval               # score agent vs naive RAG against the answer key
  python run.py graph              # print the agent graph as Mermaid
"""
import argparse
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def cmd_check(_):
    from laytime_agent import config
    from laytime_agent.llm import get_llm
    print(f"Python      : {sys.version.split()[0]}")
    print(f".env file   : {'found' if (ROOT / '.env').exists() else 'missing (copy .env.example to .env)'}")
    print(f"LLM         : {get_llm().label}")
    print(f"Embeddings  : {config.EMBEDDINGS}")
    print(f"Cases       : {sorted(p.name for p in config.CASES_DIR.iterdir() if p.is_dir())}")
    print(f"Storage dir : {config.STORE_DIR}")
    if get_llm().available:
        ok = get_llm().text("Reply with the single word OK.", "ping", max_tokens=5)
        print(f"LLM ping    : {ok!r}" if ok else "LLM ping    : FAILED - check API key / model name in .env")


def cmd_ingest(a):
    from laytime_agent import ingest
    print(ingest.ingest(reset=a.reset))


def cmd_migrate_db(_):
    from laytime_agent.migrate import migrate_sqlite_to_postgres
    counts = migrate_sqlite_to_postgres()
    for table, count in counts.items():
        print(f"{table:14}: {count}")
    print("SQLite source retained unchanged. Uploaded files, Chroma index and checkpoint history are separate stores.")


def cmd_ui(_):
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "ui" / "app.py")], cwd=ROOT)


def cmd_api(_):
    subprocess.run([sys.executable, "-m", "uvicorn", "laytime_agent.api:app", "--reload", "--port", "8000"], cwd=ROOT)


def cmd_case(a):
    from laytime_agent import service, storage
    if not storage.list_cases():
        from laytime_agent import ingest
        ingest.ingest(reset=True)
    r = service.start_run(a.case_id, auto_approve=a.auto,
                          on_event=lambda e: print(f"[{e['node']:9}] {e['kind']:10} {e['message'][:160]}"))
    if r["status"] == "awaiting_approval":
        ans = input("\nApprove the laytime statement and draft the letter? [y/N] ").strip().lower()
        r = service.decide(r["run_id"], ans == "y", approver="cli-user",
                           on_event=lambda e: print(f"[{e['node']:9}] {e['kind']:10} {e['message'][:160]}"))
    s = r["result"]
    print(f"\n{r['status'].upper()}: {s.get('result')} USD {s.get('amount_usd')}  -> outputs/{r['run_id']}/")


def cmd_eval(_):
    from evals.run_evals import main
    main()


def cmd_graph(_):
    from laytime_agent.agent.graph import mermaid
    print(mermaid())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(f=cmd_check)
    s = sub.add_parser("ingest")
    s.add_argument("--reset", action="store_true")
    s.set_defaults(f=cmd_ingest)
    sub.add_parser("migrate-db").set_defaults(f=cmd_migrate_db)
    sub.add_parser("ui").set_defaults(f=cmd_ui)
    sub.add_parser("api").set_defaults(f=cmd_api)
    s = sub.add_parser("case")
    s.add_argument("case_id")
    s.add_argument("--auto", action="store_true", help="auto-approve")
    s.set_defaults(f=cmd_case)
    sub.add_parser("eval").set_defaults(f=cmd_eval)
    sub.add_parser("graph").set_defaults(f=cmd_graph)
    args = p.parse_args()
    args.f(args)
