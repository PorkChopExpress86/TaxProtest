"""Idempotent initialization for PostgreSQL.

Usage:
  TAXPROTEST_DATABASE_URL=postgresql://... python scripts/run_init_postgres.py

Skips silently if TAXPROTEST_DATABASE_URL not set or not a Postgres URL.
"""
from __future__ import annotations

import os
from pathlib import Path
from db import get_connection

SQL_PATH = Path(__file__).parent / "init_postgres.sql"


def main() -> None:
    url = os.getenv("TAXPROTEST_DATABASE_URL")
    if not url or not url.startswith("postgres"):
        print("[init] Postgres URL not set; skipping")
        return
    if not SQL_PATH.exists():
        print(f"[init] SQL file missing: {SQL_PATH}")
        return
    sql = SQL_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.commit()
    print("[init] Postgres initialization complete (indexes ensured)")


if __name__ == "__main__":  # pragma: no cover
    main()
