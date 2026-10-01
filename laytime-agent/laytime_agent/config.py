"""Central configuration. Values come from environment variables / the .env file."""
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---- folders
DATA_DIR = ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
SHARED_DIR = DATA_DIR / "shared"
STORE_DIR = ROOT / "storage"            # created at runtime, git-ignored
DB_PATH = STORE_DIR / "laytime.db"      # SQLite: documents, logs, memory, runs, trace
CHROMA_DIR = STORE_DIR / "chroma"       # Chroma vector DB
CHECKPOINT_DB = STORE_DIR / "checkpoints.db"   # LangGraph checkpoints (pause / approve / resume)
OUTPUT_DIR = ROOT / "outputs"           # claim letters and laytime statements

# ---- LLM
# anthropic | openai | azure | mock   (mock = no API key needed; heuristics replace LLM calls)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# ---- embeddings for the vector DB
# default = Chroma's built-in MiniLM model (downloads ~80 MB once) | openai | hash (offline, lower quality)
EMBEDDINGS = os.getenv("EMBEDDINGS", "default").strip().lower()
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ---- agent behaviour
MAX_RETRIEVAL_ATTEMPTS = int(os.getenv("MAX_RETRIEVAL_ATTEMPTS", "3"))   # loop A
MAX_VERIFY_ATTEMPTS = int(os.getenv("MAX_VERIFY_ATTEMPTS", "2"))         # loop C
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "6"))
TIME_BAR_WARNING_DAYS = int(os.getenv("TIME_BAR_WARNING_DAYS", "30"))


def as_of_date() -> date:
    """Date used for time-bar checks. Override with AS_OF_DATE=YYYY-MM-DD for repeatable demos."""
    v = os.getenv("AS_OF_DATE", "").strip()
    return date.fromisoformat(v) if v else date.today()


def ensure_dirs():
    for d in (STORE_DIR, CHROMA_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
