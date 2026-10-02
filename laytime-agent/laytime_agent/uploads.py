"""Validation and staging for case documents uploaded through the UI."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pdfplumber

from . import ingest

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_BYTES = 50 * 1024 * 1024
WEATHER_COLUMNS = {"station", "timestamp_local", "precip_mm", "wind_dir", "wind_kn", "visibility_nm"}
REQUIRED_CASE_DOCS = {"charter_party", "sof", "nor"}


def _read_upload(name: str, content: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ValueError(f"Could not read PDF {name}: {exc}") from exc
    if suffix == ".csv":
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"CSV file {name} must use UTF-8 encoding.") from exc
    return ""


def stage_case_uploads(cases_root: Path, case_id: str, uploads: list[tuple[str, bytes]],
                       create_case: bool = False) -> dict:
    """Validate uploads, then save them into a case folder without replacing files."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", case_id):
        raise ValueError("Case ID must be 2-64 lowercase letters, numbers, underscores, or hyphens.")
    if not uploads:
        raise ValueError("Choose at least one document to upload.")

    root = cases_root.resolve()
    target = (root / case_id).resolve()
    if target.parent != root:
        raise ValueError("Invalid case folder.")
    if create_case and target.exists():
        raise ValueError(f"Case folder '{case_id}' already exists. Choose another Case ID or add documents to it.")
    if not create_case and not target.is_dir():
        raise ValueError(f"Case folder '{case_id}' does not exist.")

    validated = []
    types = set()
    seen_names = set()
    for name, content in uploads:
        if not name or Path(name.replace("\\", "/")).name != name:
            raise ValueError("Uploaded filenames must not contain folder paths.")
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type for {name}. Upload PDF, CSV, PNG, JPG, JPEG, or WEBP files.")
        if not content or len(content) > MAX_FILE_BYTES:
            raise ValueError(f"{name} is empty or exceeds the 50 MB per-file limit.")
        key = name.casefold()
        if key in seen_names or (target / name).exists():
            raise ValueError(f"A file named {name} already exists in this case. Rename it before uploading.")
        seen_names.add(key)

        text = _read_upload(name, content)
        doc_type = ingest.classify(Path(name), text)
        if doc_type == "weather_log":
            columns = set(next(csv.reader(io.StringIO(text)), []))
            missing = WEATHER_COLUMNS - columns
            if missing:
                raise ValueError(f"Weather CSV {name} is missing columns: {', '.join(sorted(missing))}.")
        types.add(doc_type)
        validated.append((name, content))

    if create_case:
        missing = REQUIRED_CASE_DOCS - types
        if missing:
            labels = {"charter_party": "charter party", "sof": "Statement of Facts", "nor": "Notice of Readiness"}
            raise ValueError("A new case needs a PDF for each of: " + ", ".join(labels[item] for item in sorted(missing)) + ".")

    target.mkdir(parents=True, exist_ok=not create_case)
    for name, content in validated:
        (target / name).write_bytes(content)
    return {"files": len(validated), "types": sorted(types), "folder": target}