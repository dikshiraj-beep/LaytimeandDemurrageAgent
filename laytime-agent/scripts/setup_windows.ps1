# Run from the project folder in PowerShell:  .\scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
py -3.11 -m venv .venv 2>$null; if ($LASTEXITCODE -ne 0) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env (mock mode). Edit it to add an API key." }
.\.venv\Scripts\python run.py check
.\.venv\Scripts\python run.py ingest --reset
Write-Host "`nDone. Start the UI with:  .\.venv\Scripts\python run.py ui"
