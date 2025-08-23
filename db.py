"""Lightweight database helper supporting SQLite (default) and Postgres (via psycopg).

Phase 1 (low-risk) of migration: provide unified `get_connection()` and cursor wrapper
that allows existing code using `?` param placeholders to keep working even if a
`TAXPROTEST_DATABASE_URL` (or settings.DATABASE_URL) is set.

Usage example:
    from db import get_connection, wrap_cursor
    conn = get_connection()
    cur = wrap_cursor(conn)
    cur.execute("SELECT * FROM real_acct WHERE acct = ?", (acct,))

If Postgres is active, `?` placeholders are translated to `%s` automatically.
This keeps code changes minimal until a fuller SQLAlchemy adoption.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Iterable, Optional

try:  # Attempt project settings import
    from taxprotest.config.settings import settings  # type: ignore
except Exception:  # pragma: no cover
    class _Dummy:
        DATABASE_URL: Optional[str] = os.getenv("TAXPROTEST_DATABASE_URL")
        DATABASE_PATH = os.path.join(os.getcwd(), "data", "database.sqlite")
    settings = _Dummy()  # type: ignore

_pg_available = False
try:  # psycopg3
    import psycopg  # type: ignore
    _pg_available = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore

def _is_postgres_url(url: str | None) -> bool:
    return bool(url) and url.startswith("postgres")

def get_connection(sqlite_path: str | None = None):
    """Return a DB-API connection (SQLite default, Postgres if DATABASE_URL set)."""
    url = getattr(settings, "DATABASE_URL", None) or os.getenv("TAXPROTEST_DATABASE_URL")
    if _is_postgres_url(url):
        if not _pg_available:
            raise RuntimeError("psycopg not installed but DATABASE_URL provided")
        return psycopg.connect(url)  # type: ignore
    # Fallback SQLite
    path = sqlite_path or str(getattr(settings, "DATABASE_PATH", "data/database.sqlite"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return sqlite3.connect(path)

class CursorWrapper:
    """Cursor adapter translating '?' placeholders to '%s' for Postgres."""
    def __init__(self, cursor, translate: bool):
        self._cur = cursor
        self._translate = translate

    def _adapt_sql(self, sql: str) -> str:
        if self._translate:
            return sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params: Iterable[Any] | None = None):
        sql2 = self._adapt_sql(sql)
        if params is None:
            return self._cur.execute(sql2)
        return self._cur.execute(sql2, params)

    def executemany(self, sql: str, seq_of_params):  # type: ignore[override]
        sql2 = self._adapt_sql(sql)
        return self._cur.executemany(sql2, seq_of_params)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

    def __getattr__(self, item):  # pragma: no cover
        return getattr(self._cur, item)

def wrap_cursor(conn):
    url = getattr(settings, "DATABASE_URL", None) or os.getenv("TAXPROTEST_DATABASE_URL")
    cur = conn.cursor()
    if _is_postgres_url(url):
        return CursorWrapper(cur, translate=True)
    return cur

def get_db(sqlite_path: str | None = None):
    conn = get_connection(sqlite_path)
    return conn, wrap_cursor(conn)

__all__ = ["get_connection", "wrap_cursor", "get_db"]
