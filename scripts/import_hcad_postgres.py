#!/usr/bin/env python3
"""
Bulk import HCAD tab-delimited text files into PostgreSQL using psycopg COPY.
- Auto-creates tables with TEXT columns from file headers (sanitized to snake_case)
- Uses LATIN1 encoding (works with HCAD export), tab delimiter, CSV mode with header
- Streams file in chunks to keep memory stable

Usage:
    # Import specific tables
    python scripts/import_hcad_postgres.py --tables real_acct fixtures extra_features land

    # Import a curated set (real_acct, building_res, fixtures, extra_features, land, owners)
    python scripts/import_hcad_postgres.py --all

    # Import every .txt present in text_files (owners handled specially)
    python scripts/import_hcad_postgres.py --all-present

    # Rebuild property_derived using fixtures and extra_features
    python scripts/import_hcad_postgres.py --rebuild-derived

Requires TAXPROTEST_DATABASE_URL env var pointing to Postgres.
"""

from __future__ import annotations
import argparse
import os
import re
from pathlib import Path
from typing import List

import psycopg
from psycopg import sql

BASE = Path(__file__).resolve().parents[1]
TEXT_DIR = BASE / 'text_files'

DEFAULT_TABLES = ['real_acct']
ALL_TABLES = [
    'real_acct',
    'building_res',
    'fixtures',
    'extra_features',
    'land',
    # Special-case: owners (no header); handled via import_owners()
]


def sanitize(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"[^a-z0-9_]", "_", n)
    n = re.sub(r"_+", "_", n)
    n = n.strip("_")
    if not n:
        n = "col"
    return n


def read_header(file_path: Path) -> List[str]:
    with open(file_path, 'r', encoding='latin-1', newline='') as f:
        header = f.readline().rstrip('\r\n')
    raw_cols = header.split('\t')
    cols = [sanitize(c) for c in raw_cols]
    return cols


def drop_if_exists(cur: psycopg.Cursor, table: str):
    cur.execute(sql.SQL('DROP TABLE IF EXISTS {} CASCADE').format(sql.Identifier(table)))


def create_table(cur: psycopg.Cursor, table: str, columns: List[str]):
    col_defs = sql.SQL(', ').join(sql.Composed([sql.Identifier(c), sql.SQL(' TEXT')]) for c in columns)
    cur.execute(sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(table), col_defs))


def create_index(cur: psycopg.Cursor, table: str, column: str):
    idx = f"idx_{table}_{column}"
    cur.execute(sql.SQL('CREATE INDEX IF NOT EXISTS {} ON {} ({})')
                .format(sql.Identifier(idx), sql.Identifier(table), sql.Identifier(column)))


def copy_table(conn: psycopg.Connection, file_path: Path, table: str, columns: List[str]):
    """Stream TSV rows into Postgres via COPY, normalizing row length to header length.
    - Treat as CSV with a tab delimiter.
    - Disable CSV quoting by using QUOTE as backspace (unlikely to appear).
    - Set client_encoding to LATIN1 to match file bytes.
    """
    import csv

    copy_sql = sql.SQL(
        """
        COPY {} ({})
        FROM STDIN WITH (
            FORMAT csv,
            DELIMITER E'\t',
            QUOTE E'\b',
            HEADER false
        )
        """
    ).format(sql.Identifier(table), sql.SQL(', ').join(sql.Identifier(c) for c in columns))

    total_rows = 0
    with conn.cursor() as cur:
        cur.execute("SET client_encoding TO 'LATIN1'")
        with cur.copy(copy_sql) as cp:
            with open(file_path, 'r', encoding='latin-1', newline='') as f:
                reader = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
                # skip header
                next(reader, None)
                for row in reader:
                    # Normalize to expected number of columns
                    if len(row) < len(columns):
                        row = row + [''] * (len(columns) - len(row))
                    elif len(row) > len(columns):
                        row = row[:len(columns)]
                    cp.write_row(row)
                    total_rows += 1
                    if total_rows % 200000 == 0:
                        print(f"  .. {total_rows:,} rows copied")
    return total_rows


def import_file(conn: psycopg.Connection, table: str):
    file_path = TEXT_DIR / f"{table}.txt"
    if not file_path.exists():
        print(f"⚠️  Missing file: {file_path}")
        return False

    print(f"📥 Importing {table} from {file_path.name} ...")
    cols = read_header(file_path)

    with conn.cursor() as cur:
        # Create table
        drop_if_exists(cur, table)
        create_table(cur, table, cols)
        conn.commit()

    # COPY data
    copy_table(conn, file_path, table, cols)
    conn.commit()

    # Post tasks
    with conn.cursor() as cur:
        # Helpful indexes
        if 'acct' in cols:
            create_index(cur, table, 'acct')
        if 'site_addr_1' in cols:
            create_index(cur, table, 'site_addr_1')
        cur.execute(sql.SQL('ANALYZE {}').format(sql.Identifier(table)))
        conn.commit()

        # Report count
        cur.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table)))
        count = cur.fetchone()[0]
    print(f"✅ {table}: {count:,} rows")
    return True


def import_owners(conn: psycopg.Connection) -> bool:
    """Owners file is headerless with 5 columns: acct, ln_num, name, aka, pct_own."""
    file_path = TEXT_DIR / 'owners.txt'
    if not file_path.exists():
        print("⚠️  Missing file: owners.txt")
        return False
    print("📥 Importing owners from owners.txt ...")
    with conn.cursor() as cur:
        drop_if_exists(cur, 'owners')
        cur.execute("CREATE TABLE owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
        conn.commit()
        copy_sql = sql.SQL(
            """
            COPY owners (acct, ln_num, name, aka, pct_own)
            FROM STDIN WITH (
                FORMAT csv,
                DELIMITER E'\t',
                QUOTE E'\b',
                HEADER false
            )
            """
        )
        total = 0
        with cur.copy(copy_sql) as cp:
            with open(file_path, 'r', encoding='latin-1', newline='') as f:
                import csv as _csv
                rdr = _csv.reader(f, delimiter='\t', quoting=_csv.QUOTE_NONE)
                for row in rdr:
                    row = (row[:5] + [''] * (5 - len(row)))[:5]
                    cp.write_row(row)
                    total += 1
                    if total % 200000 == 0:
                        print(f"  .. {total:,} rows copied")
        conn.commit()
        with conn.cursor() as cur2:
            cur2.execute('ANALYZE owners')
            cur2.execute('SELECT COUNT(*) FROM owners')
            cnt = cur2.fetchone()[0]
        print(f"✅ owners: {cnt:,} rows")
    return True


def list_present_tables() -> list[str]:
    """Return list of importable table names for all .txt files in text_files.
    Excludes owners here (special-cased) but includes any other headered file.
    """
    names = []
    if not TEXT_DIR.exists():
        return names
    for p in TEXT_DIR.glob('*.txt'):
        name = p.stem
        if name.lower() == 'owners':
            continue
        names.append(name)
    names.sort()
    return names


def rebuild_property_derived(conn: psycopg.Connection):
    """Rebuild property_derived with real bedrooms/bathrooms/stories/amenities.

    Sources:
      - fixtures: counts RMB/RMF/RMH/APx for beds/baths; STY/STC for stories
      - extra_features: amenities detection (POOL/GARAGE/DECK/PATIO/FIRE/SPA)
      - building_res: eff year, qa_cd, property_use_cd, im_sq_ft, gross_ar; text for garage/pool hints
    """
    print("🔧 Rebuilding property_derived …")
    with conn.cursor() as cur:
        drop_if_exists(cur, 'property_derived')
        cur.execute(
            """
            CREATE TABLE property_derived (
                acct TEXT PRIMARY KEY,
                bedrooms INTEGER,
                bathrooms REAL,
                stories INTEGER,
                property_type TEXT,
                qa_cd TEXT,
                quality_rating REAL,
                overall_rating REAL,
                rating_explanation TEXT,
                amenities TEXT,
                has_pool INTEGER,
                has_garage INTEGER
            )
            """
        )
        conn.commit()

    # Quality code to rating mapping (fallback by first letter)
    quality_rank: dict[str, float] = {'X': 10.0, 'A': 9.0, 'B': 7.0, 'C': 5.0, 'D': 3.0, 'E': 1.5, 'F': 1.0}

    # Preload fixtures counts
    fixture_counts: dict[str, dict[str, float | int | None]] = {}
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT acct, type, type_dscr, units FROM fixtures WHERE type IS NOT NULL AND units IS NOT NULL")
            for acct, ftype, tdesc, units in cur.fetchall():
                at = (acct or '').strip()
                if not at:
                    continue
                fc = fixture_counts.setdefault(at, {'bedrooms': 0, 'bathrooms': 0.0, 'stories': None, 'c_stories': None})
                try:
                    u = float(units) if units not in (None, '') else 0.0
                except Exception:
                    u = 0.0
                fupper = (ftype or '').upper()
                dupper = (tdesc or '').upper()
                if fupper == 'RMB' or 'BEDROOM' in dupper:
                    fc['bedrooms'] = int(fc['bedrooms']) + int(round(u))
                if fupper.startswith('AP') and 'BEDROOM' in dupper:
                    mult = {'AP1': 1, 'AP2': 2, 'AP3': 3, 'AP4': 4}.get(fupper, 0)
                    fc['bedrooms'] = int(fc['bedrooms']) + int(round(u)) * mult
                if fupper == 'RMF' or 'FULL BATH' in dupper:
                    fc['bathrooms'] = float(fc['bathrooms']) + u
                elif fupper == 'RMH' or 'HALF BATH' in dupper:
                    fc['bathrooms'] = float(fc['bathrooms']) + 0.5 * u
                if fupper == 'STY' and u > 0 and fc.get('stories') is None:
                    try:
                        fc['stories'] = int(round(u))
                    except Exception:
                        pass
                if fupper == 'STC' and u > 0 and fc.get('c_stories') is None:
                    try:
                        fc['c_stories'] = int(round(u))
                    except Exception:
                        pass
        except Exception:
            pass

    # Preload amenities from extra_features
    amenities_map: dict[str, list[str]] = {}
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT acct, l_dscr FROM extra_features WHERE l_dscr IS NOT NULL")
            for acct, desc in cur.fetchall():
                if not acct or not desc:
                    continue
                up = str(desc).upper()
                if any(k in up for k in ['POOL', 'GARAGE', 'DECK', 'PATIO', 'FIRE', 'SPA']):
                    amenities_map.setdefault(acct.strip(), []).append(str(desc).strip())
        except Exception:
            pass

    # Iterate building_res and compute derived values
    rows: list[tuple] = []
    with conn.cursor() as cur:
        cur.execute("SELECT acct, dscr, structure_dscr, eff, qa_cd, property_use_cd, im_sq_ft, gross_ar FROM building_res")
        for acct, dscr, sd, eff, qa_cd, puc, im_sq_ft, gross_ar in cur.fetchall():
            at = (acct or '').strip()
            if not at:
                continue
            fc = fixture_counts.get(at, {})
            beds = fc.get('bedrooms') if fc else None
            baths = fc.get('bathrooms') if fc else None
            stories = fc.get('stories') if fc and fc.get('stories') is not None else fc.get('c_stories') if fc else None
            # Heuristic backup using gross area ratio
            if stories is None:
                try:
                    if im_sq_ft and gross_ar and im_sq_ft not in ('', '0') and gross_ar not in ('', '0'):
                        ratio = float(gross_ar) / float(im_sq_ft)
                        if 1.0 <= ratio <= 4.0:
                            stories = int(round(ratio))
                except Exception:
                    pass

            qa = (qa_cd or '').strip()
            q_rating = quality_rank.get(qa[:1], None)
            age_score = None
            try:
                if eff and str(eff).isdigit():
                    from datetime import datetime as _dt
                    age = max(0, _dt.now().year - int(eff))
                    age_score = max(1.0, min(10.0, 10 - age * 0.05))
            except Exception:
                pass
            overall = None
            if q_rating is not None and age_score is not None:
                overall = round(q_rating * 0.7 + age_score * 0.3, 1)
            elif q_rating is not None:
                overall = q_rating
            elif age_score is not None:
                overall = age_score

            # Property type from property_use_cd (best-effort)
            ptype = None
            if puc:
                if str(puc).startswith('R'):
                    ptype = 'Residential'
                elif str(puc).startswith('C'):
                    ptype = 'Commercial'
                else:
                    ptype = None

            # Compose rating explanation
            expl = None
            if overall is not None:
                parts = []
                if q_rating is not None:
                    parts.append(f"quality {qa or 'NA'} ({q_rating}/10)")
                if age_score is not None and eff:
                    parts.append(f"age ({eff}, {age_score:.1f}/10)")
                expl = ("Score: " + ', '.join(parts))[:180]

            amenities = None
            has_pool = 0
            has_garage = 0
            if at in amenities_map:
                al = amenities_map[at][:5]
                amenities = ', '.join(al) if al else None
                upc = ' '.join(al).upper()
                if 'POOL' in upc:
                    has_pool = 1
                if 'GARAGE' in upc and 'NO GARAGE' not in upc:
                    has_garage = 1
            # Backup: scan building descriptions
            desc_combo = ' '.join(filter(None, [dscr or '', sd or ''])).upper()
            if has_garage == 0 and 'GARAGE' in desc_combo and 'NO GARAGE' not in desc_combo:
                has_garage = 1
            if has_pool == 0 and 'POOL' in desc_combo:
                has_pool = 1

            rows.append((at, beds, baths, stories, ptype, qa, q_rating, overall, expl, amenities, has_pool, has_garage))

    # Bulk insert
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO property_derived (
                acct, bedrooms, bathrooms, stories, property_type, qa_cd, quality_rating,
                overall_rating, rating_explanation, amenities, has_pool, has_garage
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            rows,
        )
        create_index(cur, 'property_derived', 'acct')
        try:
            create_index(cur, 'property_derived', 'bedrooms')
        except Exception:
            pass
        conn.commit()
    print(f"✅ property_derived rebuilt with {len(rows):,} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', nargs='*', help='Tables to import (default: real_acct)')
    ap.add_argument('--all', action='store_true', help='Import all common HCAD tables')
    ap.add_argument('--all-present', action='store_true', help='Import all .txt files present in text_files (owners handled separately)')
    ap.add_argument('--rebuild-derived', action='store_true', help='Rebuild property_derived from fixtures/extra_features')
    args = ap.parse_args()

    dsn = os.environ.get('TAXPROTEST_DATABASE_URL')
    if not dsn:
        raise SystemExit('TAXPROTEST_DATABASE_URL not set')

    tables = DEFAULT_TABLES
    if args.all_present:
        tables = list_present_tables()
    elif args.all:
        tables = ALL_TABLES
    elif args.tables:
        tables = args.tables

    print(f"Connecting to Postgres...")
    with psycopg.connect(dsn) as conn:
        for t in tables:
            if t.lower() == 'owners':
                import_owners(conn)
            else:
                import_file(conn, t)

        if args.rebuild_derived:
            rebuild_property_derived(conn)

    print("All done.")


if __name__ == '__main__':
    main()
