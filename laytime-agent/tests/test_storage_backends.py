from pathlib import Path

import pytest

from laytime_agent import config, migrate, storage


def test_sql_placeholders_follow_selected_backend(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "")
    assert storage._sql("SELECT * FROM runs WHERE run_id=?") == "SELECT * FROM runs WHERE run_id=?"

    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://unused")
    assert storage._sql("SELECT * FROM runs WHERE run_id=? AND status=?") == (
        "SELECT * FROM runs WHERE run_id=%s AND status=%s"
    )


def test_upsert_generates_portable_conflict_statement(monkeypatch):
    called = []
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(storage, "execute", lambda statement, values: called.append((statement, values)))

    storage.upsert("ports", ("port", "info"), ("Port A", "{}"), ("port",))

    assert "ON CONFLICT (port) DO UPDATE SET info=excluded.info" in called[0][0]
    assert called[0][1] == ("Port A", "{}")


def test_migration_requires_postgres_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        migrate.migrate_sqlite_to_postgres(tmp_path / "missing.db")


def test_migration_checks_for_source_before_connecting(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://unused")
    with pytest.raises(FileNotFoundError):
        migrate.migrate_sqlite_to_postgres(tmp_path / "missing.db")