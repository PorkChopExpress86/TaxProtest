"""Unified ingestion for Postgres inside Docker.

Runs:
  1. init_postgres.sql (indexes, extensions, geom column if defined there)
  2. text data import via extract_data (COPY fast paths)
  3. geo import via load_geo_data (creates property_geo with geom)

Idempotent: DROP/CREATE for property_geo; text tables overwritten.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

START = time.time()
DB_URL = os.getenv("TAXPROTEST_DATABASE_URL", "")
if not DB_URL.startswith("postgres"):
    print("❌ TAXPROTEST_DATABASE_URL must be a Postgres URL for ingestion.")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]

print("🔧 Step 1: PostgreSQL init script (extensions / indexes)...")
try:
    from scripts.run_init_postgres import main as init_main  # type: ignore
    init_main()
    print("✅ Init script complete")
except Exception as e:
    print(f"⚠️ Init script issue: {e}")

print("📥 Step 2: Text data import (COPY paths)...")
try:
    import extract_data  # triggers load when run as script; we'll call function directly
    extract_data.load_data_to_sqlite()  # name retained; adapts to Postgres via env
    print("✅ Text data loaded")
except Exception as e:
    print(f"❌ Text import failed: {e}")
    sys.exit(2)

print("🌍 Step 3: Geo import (property_geo with geom)...")
try:
    import load_geo_data
    load_geo_data.load_geo_data()
    print("✅ Geo data loaded")
except Exception as e:
    print(f"⚠️ Geo import issue: {e}")

# Simple row count summary
try:
    from db import get_connection, wrap_cursor
    with get_connection() as conn:
        cur = wrap_cursor(conn)
        for tbl in ["real_acct", "building_res", "owners", "property_geo"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                print(f"   {tbl}: {cur.fetchone()[0]:,} rows")
            except Exception:
                print(f"   {tbl}: (missing)")
except Exception as e:
    print(f"⚠️ Verification skipped: {e}")

print(f"⏱️ Total ingestion time: {time.time()-START:.1f}s")
