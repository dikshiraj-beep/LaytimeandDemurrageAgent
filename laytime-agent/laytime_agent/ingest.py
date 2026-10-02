"""Ingestion: reads data/cases and data/shared, stores documents + reference data in SQLite,
splits contracts into clause-aware chunks and indexes them in the Chroma vector DB.

Run:  python run.py ingest        (add --reset to rebuild from scratch)
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from . import config, storage, vectorstore

log = logging.getLogger("laytime.ingest")

# document type -> precedence used when two documents give different values for the same term
PRECEDENCE = {"recap": 3, "rider": 2, "charter_party": 1, "negotiation": 0, "company_terms": -1}
BANNER = re.compile(r"^SYNTHETIC SAMPLE DOCUMENT.*$", re.M)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    return BANNER.sub("", text).strip()


def classify(path: Path, text: str) -> str:
    head = (text.strip().splitlines() or [""])[0].upper()     # document title line
    name = path.name.lower()
    if path.suffix.lower() in IMAGE_EXT:
        return "image"
    if path.suffix.lower() == ".csv":
        return "weather_log" if "precip" in text[:200].lower() else "table"
    if "NOTICE OF READINESS" in head:
        return "nor"
    if "STATEMENT OF FACTS" in head:
        return "sof"
    if "NEGOTIATION EMAIL TRAIL" in head or "negotiation" in name:
        return "negotiation"
    if "FIXTURE RECAP" in head or "recap" in name:
        return "recap"
    if "RIDER" in head:
        return "rider"
    if "CHARTER PARTY" in head:
        return "charter_party"
    if "NOTICE OF READINESS" in head:
        return "nor"
    if "STATEMENT OF FACTS" in head:
        return "sof"
    if "STANDARD LAYTIME TERMS" in head:
        return "company_terms"
    return "other"


# ------------------------------------------------------------------ chunkers
def chunk_charter_party(text):
    parts = re.split(r"(?m)^(\d{1,2})\.\s+([A-Z][^\n]{2,90})$", text)
    out = []
    if parts[0].strip():
        out.append(("Header", "Preamble", parts[0].strip()))
    for i in range(1, len(parts) - 2, 3):
        out.append((f"Cl. {parts[i]}", f"{parts[i]}. {parts[i + 1].strip()}", parts[i + 2].strip()))
    return out


def chunk_recap(text):
    out, cur_label, cur = [], "Header", []
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Za-z/ ]{1,30}(?:\([^)]{0,30}\))?):\s+(.*)$", line)
        if m:
            if cur:
                out.append((cur_label, cur_label, " ".join(cur).strip()))
            cur_label, cur = m.group(1).strip(), [line]
        else:
            cur.append(line)
    if cur:
        out.append((cur_label, cur_label, " ".join(cur).strip()))
    return [(f"Recap: {lab}", lab, body) for lab, _, body in out]


def chunk_negotiation(text):
    parts = re.split(r"(?m)^Message (\d+)\s*$", text)
    out = []
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1].strip()
        date = re.search(r"Date (.+)", body)
        subj = re.search(r"Subject (.+)", body)
        out.append((f"Email {parts[i]}", f"Email {parts[i]} - {date.group(1) if date else ''} - "
                    f"{subj.group(1) if subj else ''}", body))
    return out


def chunk_company_terms(text):
    parts = re.split(r"(?m)^(7\.\d+)\s+([^\n]+)$", text)
    return [(f"Manual {parts[i]}", f"{parts[i]} {parts[i + 1]}", parts[i + 2].strip())
            for i in range(1, len(parts) - 2, 3)]


CHUNKERS = {"charter_party": chunk_charter_party, "rider": chunk_charter_party, "recap": chunk_recap,
            "negotiation": chunk_negotiation, "company_terms": chunk_company_terms}


def sof_header(text: str) -> dict:
    def grab(label):
        m = re.search(label + r"\s+(.+)", text)
        return m.group(1).strip() if m else ""
    port = grab(r"Port / berth").split("/")[0].strip()
    return {"vessel": grab(r"Vessel").split("(")[0].strip(), "port": port,
            "operation": grab(r"Operation"), "charterers": grab(r"Charterers")}


def source_fingerprint() -> str:
    """Hash the case and shared files that the ingestion pipeline reads."""
    digest = hashlib.sha256()
    shared_inputs = {"port_holidays_2026.csv", "port_information.json", "past_claims_history.json"}
    for label, folder in (("cases", config.CASES_DIR), ("shared", config.SHARED_DIR)):
        if not folder.exists():
            continue
        for path in sorted(item for item in folder.rglob("*") if item.is_file()):
            if label == "shared" and path.suffix.lower() != ".pdf" and path.name not in shared_inputs:
                continue
            relative = path.relative_to(folder).as_posix()
            digest.update(f"{label}/{relative}\0".encode("utf-8"))
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def sources_changed() -> bool:
    """Return whether files on disk differ from the last successful ingest."""
    manifest = config.STORE_DIR / "indexed_sources.sha256"
    if not manifest.is_file():
        return True
    return manifest.read_text(encoding="ascii").strip() != source_fingerprint()


def _record_indexed_sources() -> None:
    manifest = config.STORE_DIR / "indexed_sources.sha256"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(source_fingerprint() + "\n", encoding="ascii")


# ------------------------------------------------------------------ main
def ingest(reset: bool = False) -> dict:
    config.ensure_dirs()
    storage.init_db(reset=reset)
    if reset:
        vectorstore.reset_collection()
    stats = {"cases": 0, "documents": 0, "chunks": 0, "weather_rows": 0}
    all_chunks = []

    def add_doc(case_id, path: Path):
        text = "" if path.suffix.lower() in IMAGE_EXT else (
            pdf_text(path) if path.suffix.lower() == ".pdf" else path.read_text(encoding="utf-8"))
        dtype = classify(path, text)
        doc_id = f"{case_id}/{path.name}"
        prec = PRECEDENCE.get(dtype, -2)
        storage.upsert("documents", ("doc_id", "case_id", "path", "filename", "doc_type", "precedence", "text"),
                   (doc_id, case_id, str(path.relative_to(config.ROOT)), path.name, dtype, prec, text), ("doc_id",))
        stats["documents"] += 1
        chunker = CHUNKERS.get(dtype)
        pieces = chunker(text) if chunker else ([("Full text", path.stem, text)] if text and dtype in ("nor", "sof", "other") else [])
        for n, (ref, title, body) in enumerate(pieces):
            if not body:
                continue
            c = {"chunk_id": f"{doc_id}#{n}", "doc_id": doc_id, "case_id": case_id, "doc_type": dtype,
                 "precedence": prec, "ref": ref, "title": title, "text": body}
            storage.upsert("chunks", tuple(c.keys()), tuple(c.values()), ("chunk_id",))
            all_chunks.append(c)
        if dtype == "weather_log":
            storage.execute("DELETE FROM weather WHERE case_id=?", (case_id,))
            with open(path, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    storage.execute("INSERT INTO weather VALUES (?,?,?,?,?,?,?,?)",
                                    (case_id, r["station"], r["timestamp_local"], float(r["precip_mm"] or 0),
                                     r["wind_dir"], int(r["wind_kn"] or 0), float(r["visibility_nm"] or 0),
                                     r.get("remarks", "")))
                    stats["weather_rows"] += 1
        return dtype, text

    # ---- cases
    for folder in sorted(p for p in config.CASES_DIR.iterdir() if p.is_dir()):
        case_id = folder.name
        meta = {}
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                dtype, text = add_doc(case_id, path)
                if dtype == "sof":
                    meta = sof_header(text)
        storage.upsert("cases", ("case_id", "folder", "vessel", "port", "operation", "charterers", "ingested_at"),
                   (case_id, str(folder.relative_to(config.ROOT)), meta.get("vessel"), meta.get("port"),
                meta.get("operation"), meta.get("charterers"), datetime.now().isoformat(timespec="seconds")),
                   ("case_id",))
        stats["cases"] += 1

    # ---- shared reference data
    sh = config.SHARED_DIR
    for path in sorted(sh.glob("*.pdf")):
        add_doc("shared", path)
    hol = sh / "port_holidays_2026.csv"
    if hol.exists():
        storage.execute("DELETE FROM holidays")
        with open(hol, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                storage.execute("INSERT INTO holidays VALUES (?,?,?)", (r["port"], r["date"], r["holiday"]))
    ports = sh / "port_information.json"
    if ports.exists():
        for name, info in json.loads(ports.read_text(encoding="utf-8")).items():
            storage.upsert("ports", ("port", "info"), (name, json.dumps(info)), ("port",))
    claims = sh / "past_claims_history.json"
    if claims.exists():
        for c in json.loads(claims.read_text(encoding="utf-8")):
            storage.upsert("past_claims", ("claim_id", "vessel", "counterparty", "port", "claimed_usd",
                                            "settled_usd", "status", "lessons"),
                           (c["claim_id"], c["vessel"], c["counterparty"], c["port"], c["claimed_usd"],
                            c["settled_usd"], c["status"], c["lessons"]), ("claim_id",))

    vectorstore.add_chunks(all_chunks)
    stats["chunks"] = len(all_chunks)
    stats["embeddings"] = vectorstore.embedding_kind()
    _record_indexed_sources()
    return stats
