"""One-time migration of local SQLite records into an empty PostgreSQL database."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql

from . import config, storage

TABLES = (
    "cases",
    "documents",
    "chunks",
    "weather",
    "holidays",
    "ports",
    "past_claims",
    "lessons",
    "runs",
    "trace",
)


def migrate_sqlite_to_postgres(source: Path | None = None) -> dict:
    """Copy application records from SQLite to an empty configured PostgreSQL database.

    The source is retained unchanged. Files, Chroma embeddings, and graph checkpoints
    are separate stores and are not copied by this operation.
    """
    if not config.DATABASE_URL:
        raise RuntimeError("Set DATABASE_URL in the local .env file before migrating.")
    source = source or config.DB_PATH
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source database does not exist: {source}")

    storage.init_db()
    source_conn = sqlite3.connect(source)
    source_conn.row_factory = sqlite3.Row
    destination = storage.connect()
    try:
        existing = {
            table: destination.execute(sql.SQL("SELECT COUNT(*) AS count FROM {}").format(
                sql.Identifier(table)
            )).fetchone()["count"]
            for table in TABLES
        }
        if any(existing.values()):
            raise RuntimeError(
                "Refusing to merge into a non-empty PostgreSQL database. "
                "Back up the target and use a new empty laytime_agent database."
            )
        destination.commit()

        counts = {}
        with destination.transaction():
            for table in TABLES:
                rows = source_conn.execute(f'SELECT * FROM "{table}"').fetchall()
                if not rows:
                    counts[table] = 0
                    continue
                columns = rows[0].keys()
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                with destination.cursor() as cursor:
                    cursor.executemany(statement, [tuple(row) for row in rows])
                counts[table] = len(rows)

            lesson_count = counts.get("lessons", 0)
            if lesson_count:
                destination.execute(
                    "SELECT setval(pg_get_serial_sequence('lessons', 'id'), "
                    "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM lessons"
                )
        return counts
    finally:
        source_conn.close()
        destination.close()
