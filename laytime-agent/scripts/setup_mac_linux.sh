#!/usr/bin/env bash
# Run from the project folder:  bash scripts/setup_mac_linux.sh
set -e
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env (mock mode). Edit it to add an API key."; }
./.venv/bin/python run.py check
./.venv/bin/python run.py ingest --reset
echo; echo "Done. Start the UI with:  ./.venv/bin/python run.py ui"
