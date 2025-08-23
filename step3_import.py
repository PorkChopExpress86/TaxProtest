"""
Step 3: Import Harris County Tax Data into SQLite
===============================================

This script imports extracted text files into SQLite database with amenities
processing and tracks import hashes to avoid unnecessary re-imports.
"""

import csv
import argparse
import hashlib
import json
import os
import sqlite3  # kept for catching OperationalError under SQLite
import os as _os
from db import get_connection, wrap_cursor
import importlib
import extract_data
import load_geo_data
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEXT_FILES_DIR = BASE_DIR / "text_files"
DB_PATH = BASE_DIR / 'data' / 'database.sqlite'
USING_POSTGRES = (_os.getenv("TAXPROTEST_DATABASE_URL", "").startswith("postgres"))
DEFER_INDEXES = _os.getenv("TAXPROTEST_DEFER_INDEXES", "1").lower() in {"1","true","yes"}
HASH_FILE = BASE_DIR / "data" / "import_hashes.json"
SUMMARY_FILE = BASE_DIR / "data" / "last_import_report.json"

# Whitelist of residential state_class codes to retain (single-family, condo/townhome, multi-family)
RESIDENTIAL_STATE_CLASSES = {
    'A1','A2','A3','A4',  # Single family variants
    'C1','C2','C3',       # Condo / townhome style codes (adjust if needed)
    'M1','M2','M3','M4'   # Multi-family tiers (present codes will be kept)
}

# Land use codes considered residential (include vacant 1000 by default)
RESIDENTIAL_LAND_USE_CODES = {'1000','1001','2001'}

# Ensure data directory exists
(BASE_DIR / "data").mkdir(exist_ok=True)

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_existing_hashes():
    """Load existing import hash data from JSON file"""
    if HASH_FILE.exists():
        try:
            with open(HASH_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {}

def save_hashes(hash_data):
    """Save import hash data to JSON file"""
    with open(HASH_FILE, 'w') as f:
        json.dump(hash_data, f, indent=2)

# ----------------------------- Geo / Index Helpers -----------------------------
def load_parcels_csv_into_property_geo(parcels_csv: Path) -> Optional[int]:
    """(Re)create property_geo table from a parcels.csv file. Returns row count or None if not loaded."""
    if not parcels_csv.exists():
        print(f"⚠️  parcels.csv not found at {parcels_csv}; cannot build property_geo.")
        return None
    try:
        df = pd.read_csv(parcels_csv)
        expected_cols = {"acct", "latitude", "longitude"}
        # Case-insensitive rename
        rename_map = {}
        for col in df.columns:
            l = col.lower()
            if l in expected_cols and col != l:
                rename_map[col] = l
        if rename_map:
            df = df.rename(columns=rename_map)
        df.columns = [c.lower() for c in df.columns]
        if not expected_cols.issubset(df.columns):
            print("⚠️  parcels.csv missing required columns acct, latitude, longitude")
            return None
        df = df[list(expected_cols)]
        df['acct'] = df['acct'].astype(str).str.strip().str.replace(r'[^0-9]','', regex=True).str.zfill(13)
        df = df.drop_duplicates(subset=['acct']).dropna(subset=['latitude','longitude'])
        conn = get_connection(str(DB_PATH))
        # Bulk path for Postgres using COPY for significant speed-up vs INSERT/ORM/pandas
        if USING_POSTGRES:
            try:
                raw_cur = conn.cursor()  # psycopg cursor
                raw_cur.execute('DROP TABLE IF EXISTS property_geo')
                raw_cur.execute('CREATE TABLE property_geo (acct TEXT PRIMARY KEY, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION)')
                # COPY protocol (no header)
                if hasattr(raw_cur, 'copy'):
                    try:
                        with raw_cur.copy("COPY property_geo (acct, latitude, longitude) FROM STDIN WITH (FORMAT csv)") as copy:  # type: ignore[attr-defined]
                            for row in df.itertuples(index=False):
                                copy.write_row([row.acct, row.latitude, row.longitude])
                    except Exception as _cpe:
                        print(f"⚠️  COPY streaming failed ({_cpe}); falling back to buffer method.")
                        import io, csv as _csv
                        buf = io.StringIO()
                        w = _csv.writer(buf)
                        for row in df.itertuples(index=False):
                            w.writerow([row.acct, row.latitude, row.longitude])
                        buf.seek(0)
                        raw_cur.execute("COPY property_geo (acct, latitude, longitude) FROM STDIN WITH (FORMAT csv)", buf.read())
                else:
                    import io, csv as _csv
                    buf = io.StringIO()
                    w = _csv.writer(buf)
                    for row in df.itertuples(index=False):
                        w.writerow([row.acct, row.latitude, row.longitude])
                    buf.seek(0)
                    raw_cur.execute("COPY property_geo (acct, latitude, longitude) FROM STDIN WITH (FORMAT csv)", buf.read())
                raw_cur.execute('CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)')
                conn.commit(); raw_cur.close(); conn.close()
            except Exception as pg_e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                try: conn.close()
                except Exception: pass
                print(f"⚠️  Postgres bulk load fallback due to error: {pg_e}; attempting pandas to_sql path.")
                # Fallback to original (pandas) method via a new connection
                conn2 = get_connection(str(DB_PATH))
                cur = wrap_cursor(conn2)
                cur.execute('DROP TABLE IF EXISTS property_geo')
                cur.execute('CREATE TABLE property_geo (acct TEXT PRIMARY KEY, latitude REAL, longitude REAL)')
                df.to_sql('property_geo', conn2, if_exists='append', index=False)
                cur.execute('CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)')
                conn2.commit(); conn2.close()
        else:
            cur = wrap_cursor(conn)
            cur.execute('DROP TABLE IF EXISTS property_geo')
            cur.execute('CREATE TABLE property_geo (acct TEXT PRIMARY KEY, latitude REAL, longitude REAL)')
            df.to_sql('property_geo', conn, if_exists='append', index=False)
            cur.execute('CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)')
            conn.commit(); conn.close()
        print(f"✅ Imported {len(df):,} parcel geo records into property_geo table.")
        return len(df)
    except Exception as e:
        print(f"❌ Error rebuilding property_geo from parcels.csv: {e}")
        return None

def ensure_property_geo(force: bool = False):
    """Ensure property_geo table exists; rebuild from parcels.csv when missing or forced.

    force: if True rebuild unconditionally from parcels.csv.
    """
    parcels_csv = BASE_DIR / "extracted" / "gis" / "parcels.csv"
    needs_rebuild = force
    if not needs_rebuild:
        if not DB_PATH.exists():
            print("⚠️  Database missing; cannot ensure property_geo yet.")
            return
        try:
            if USING_POSTGRES:
                # Postgres path: skip property_geo ensure heuristics for now (handled separately if needed)
                return
            conn = get_connection(str(DB_PATH))
            cur = wrap_cursor(conn)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_geo'")
            exists = cur.fetchone() is not None
            if not exists:
                print("ℹ️  property_geo table missing; will rebuild.")
                needs_rebuild = True
            else:
                cur.execute("SELECT COUNT(*) FROM property_geo")
                count = cur.fetchone()[0]
                if count < 1000:  # heuristically too small for full dataset
                    print(f"ℹ️  property_geo has only {count} rows; rebuilding from parcels.csv.")
                    needs_rebuild = True
        finally:
            try:
                cur.close(); conn.close()
            except Exception:
                pass
    if needs_rebuild:
        load_parcels_csv_into_property_geo(parcels_csv)
        # If we rebuilt geo late, re-run spatial index creation if Postgres
        if USING_POSTGRES and DEFER_INDEXES:
            try:
                conn = get_connection(str(DB_PATH))
                create_deferred_indexes(conn)
                conn.close()
            except Exception:
                pass

def verify_database_integrity():
    """Run basic integrity checks and ensure core indexes exist."""
    if not DB_PATH.exists() and not USING_POSTGRES:
        print("⚠️  No database file to verify.")
        return
    conn = get_connection(str(DB_PATH))
    cur = wrap_cursor(conn)
    try:
        print("🔎 Verifying database integrity...")
        if not USING_POSTGRES:
            cur.execute("PRAGMA integrity_check")
            result = cur.fetchone()
            if result and result[0] == 'ok':
                print("   ✅ integrity_check OK")
            else:
                print(f"   ❌ integrity_check failed: {result}")
        else:
            # Minimal Postgres check
            try:
                cur.execute("SELECT 1")
                _ = cur.fetchone()
                print("   ✅ basic connectivity OK")
            except Exception as e:  # pragma: no cover
                print(f"   ❌ connectivity check failed: {e}")
        # Ensure critical indexes (idempotent)
        index_sqls = [
            "CREATE INDEX IF NOT EXISTS idx_real_acct_acct ON real_acct(acct)",
            "CREATE INDEX IF NOT EXISTS idx_building_res_acct ON building_res(acct)",
            "CREATE INDEX IF NOT EXISTS idx_property_derived_acct ON property_derived(acct)",
            "CREATE INDEX IF NOT EXISTS idx_real_acct_addr ON real_acct(site_addr_1)",
            "CREATE INDEX IF NOT EXISTS idx_real_acct_zip ON real_acct(site_addr_3)"
        ]
        for sql_stmt in index_sqls:
            try:
                cur.execute(sql_stmt)
            except Exception as e:
                print(f"   ⚠️  Index creation warning: {e}")
        conn.commit()
    finally:
        try:
            cur.close(); conn.close()
        except Exception:
            pass

def create_table_from_csv(cursor, table_name: str, csv_path: Path, encoding='mbcs'):
    """Create table schema by reading first few rows of CSV"""
    try:
        with open(csv_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            headers = next(reader)
            
        # Clean column names (remove special chars, spaces)
        clean_headers = []
        for h in headers:
            clean_h = ''.join(c if c.isalnum() else '_' for c in h)
            clean_headers.append(clean_h)
        
        # Create table with TEXT columns (SQLite is flexible)
        columns = ', '.join(f'"{h}" TEXT' for h in clean_headers)
        cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
        cursor.execute(f'CREATE TABLE {table_name} ({columns})')
        
        return clean_headers
    except UnicodeDecodeError:
        if encoding != 'utf-8':
            return create_table_from_csv(cursor, table_name, csv_path, encoding='utf-8')
        raise

def load_csv_to_table(cursor, table_name: str, csv_path: Path, headers: list, encoding='mbcs', batch_size=10000):
    """Load CSV data into SQLite table in batches"""
    # Increase CSV field size limit to handle very large fields
    csv.field_size_limit(10000000)  # 10MB limit
    
    try:
        with open(csv_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)  # Skip header row
            
            batch = []
            total_rows = 0
            for row_num, row in enumerate(reader, 1):
                # Pad or truncate row to match headers
                normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                batch.append(normalized_row)
                
                if len(batch) >= batch_size:
                    placeholders = ', '.join(['?' for _ in headers])
                    cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                    total_rows += len(batch)
                    print(f"    Inserted {total_rows:,} rows...", end='\r')
                    batch = []
            
            # Insert remaining rows
            if batch:
                placeholders = ', '.join(['?' for _ in headers])
                cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                total_rows += len(batch)
                
            print(f"    ✅ Inserted {total_rows:,} total rows")
                
    except UnicodeDecodeError:
        if encoding != 'utf-8':
            load_csv_to_table(cursor, table_name, csv_path, headers, encoding='utf-8', batch_size=batch_size)
        else:
            raise

def create_property_derived_table(cursor):
    """Create the property_derived table with amenities support"""
    cursor.execute("DROP TABLE IF EXISTS property_derived")
    cursor.execute("""
        CREATE TABLE property_derived (
            acct TEXT PRIMARY KEY,
            bedrooms TEXT,
            bathrooms TEXT,
            property_type TEXT,
            qa_cd TEXT,
            quality_rating REAL,
            overall_rating REAL,
            rating_explanation TEXT,
            amenities TEXT
        )
    """)

def load_amenities_data(cursor):
    """Pre-load amenities data for efficient processing"""
    amenities_data = {}
    
    try:
        print("  Loading amenities data...")
        cursor.execute("SELECT acct, l_dscr FROM extra_features")
        for acct, desc in cursor.fetchall():
            if any(keyword in desc.upper() for keyword in ['POOL', 'GARAGE', 'DECK', 'PATIO', 'FIRE', 'SPA']):
                acct_trimmed = acct.strip()
                if acct_trimmed not in amenities_data:
                    amenities_data[acct_trimmed] = []
                amenities_data[acct_trimmed].append(desc)
        print(f"  ✅ Loaded amenities for {len(amenities_data)} properties")
    except sqlite3.OperationalError:
        print("  ⚠️  extra_features table not found, amenities will be empty")
    
    return amenities_data

def populate_property_derived(cursor):
    """Populate property_derived table with bedroom/bathroom and amenities data"""
    print("  Creating property_derived table...")
    create_property_derived_table(cursor)
    
    # Pre-load amenities and fixtures data
    amenities_data = load_amenities_data(cursor)
    
    # Pre-load fixtures data for bedrooms/bathrooms  
    fixtures_data = {}
    try:
        print("  Loading bedroom/bathroom data...")
        cursor.execute("SELECT acct, type_dscr FROM fixtures")
        for acct, desc in cursor.fetchall():
            acct_trimmed = acct.strip()
            if acct_trimmed not in fixtures_data:
                fixtures_data[acct_trimmed] = []
            fixtures_data[acct_trimmed].append(desc)
        print(f"  ✅ Loaded bed/bath data for {len(fixtures_data)} properties")
    except sqlite3.OperationalError:
        print("  ⚠️  fixtures table not found, bed/bath data will be empty")
    
    # Process all accounts from real_acct
    print("  Processing property data...")
    cursor.execute("SELECT acct FROM real_acct")
    accounts = cursor.fetchall()
    
    rows = []
    batch_size = 10000
    processed = 0
    
    for (acct,) in accounts:
        # Extract bedroom/bathroom data
        bedrooms = None
        bathrooms = None
        acct_trimmed = acct.strip()
        
        if acct_trimmed in fixtures_data:
            for desc in fixtures_data[acct_trimmed]:
                desc_upper = desc.upper()
                if 'BEDROOM' in desc_upper or 'BED ROOM' in desc_upper:
                    try:
                        bedrooms = int(''.join(filter(str.isdigit, desc)))
                    except (ValueError, TypeError):
                        pass
                elif 'BATHROOM' in desc_upper or 'BATH ROOM' in desc_upper:
                    try:
                        bathrooms = int(''.join(filter(str.isdigit, desc)))
                    except (ValueError, TypeError):
                        pass
        
        # Determine property type and ratings (simplified)
        prop_type = "Residential"  # Default
        qa_cd = None
        quality_rating = None
        overall_rating = None
        rating_expl = None
        
        # Extract amenities from pre-loaded data
        amenities = None
        if acct_trimmed in amenities_data:
            amenity_list = amenities_data[acct_trimmed][:5]  # Limit to first 5 amenities
            amenities = ', '.join(amenity_list) if amenity_list else None
        
        rows.append((acct.strip(), bedrooms, bathrooms, prop_type, qa_cd, 
                    quality_rating, overall_rating, rating_expl, amenities))
        
        if len(rows) >= batch_size:
            cursor.executemany("INSERT INTO property_derived VALUES (?,?,?,?,?,?,?,?,?)", rows)
            processed += len(rows)
            print(f"    Processed {processed:,} properties...", end='\r')
            rows = []
    
    # Insert remaining rows
    if rows:
        cursor.executemany("INSERT INTO property_derived VALUES (?,?,?,?,?,?,?,?,?)", rows)
        processed += len(rows)
    
    print(f"    ✅ Processed {processed:,} total properties")
    

def import_data_to_sqlite():
    """Main import function"""
    # Ensure required files exist before delegating to extract_data
    core_files = {
        "real_acct": TEXT_FILES_DIR / "real_acct.txt",
        "building_res": TEXT_FILES_DIR / "building_res.txt",
    }

    for table, path in core_files.items():
        if not path.exists():
            print(f"❌ CRITICAL: {table} file not found at {path}")
            print("   Cannot proceed without core files. Run step2_extract.py first.")
            return False

    # Delegate the full import and derived metrics work to extract_data (it contains the richer logic)
    try:
        print("📥 Delegating import to extract_data.load_data_to_sqlite()...")
        importlib.reload(extract_data)
        try:
            import csv as _csv
            try:
                _csv.field_size_limit(10_000_000)
            except Exception:
                pass
        except Exception:
            pass
        extract_data.load_data_to_sqlite()
    except Exception as e:
        print(f"❌ Error delegating import to extract_data: {e}")
        return False

    # Attempt to load land.txt if present (not handled in extract_data)
    land_path = TEXT_FILES_DIR / 'land.txt'
    if land_path.exists():
        try:
            print("Loading land from", land_path, "...")
            conn_tmp = get_connection(str(DB_PATH))
            cur_tmp = wrap_cursor(conn_tmp)
            headers = create_table_from_csv(cur_tmp, 'land', land_path)
            load_csv_to_table(cur_tmp, 'land', land_path, headers)
            try:
                cur_tmp.execute('CREATE INDEX IF NOT EXISTS idx_land_acct ON land(acct)')
                cur_tmp.execute('CREATE INDEX IF NOT EXISTS idx_land_usecd ON land(use_cd)')
            except Exception:
                pass
            conn_tmp.commit(); conn_tmp.close()
            print("  ✅ land table loaded")
        except Exception as e:
            print(f"  ⚠️  Could not load land.txt: {e}")
    else:
        print("  ⚠️  land.txt not found; land use filter will rely solely on state_class.")

    # Filter to residential-only scope before index creation
    def prune_to_residential(conn):
        try:
            if USING_POSTGRES:
                return
            cur = conn.cursor()
            # Ensure state_class column exists
            cur.execute("PRAGMA table_info(real_acct)")
            cols = [c[1].lower() for c in cur.fetchall()]
            if 'state_class' not in cols:
                print("⚠️  state_class column not found; skipping residential pruning.")
                return
            # Build temporary set of residential land accounts if land table present
            has_land = False
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='land'")
                has_land = cur.fetchone() is not None
            except Exception:
                has_land = False
            land_clause = ''
            if has_land:
                placeholders_land = ','.join(['?']*len(RESIDENTIAL_LAND_USE_CODES))
                # Create temp table of residential land accounts for performance
                try:
                    cur.execute('DROP TABLE IF EXISTS _res_land_accts')
                    cur.execute(f"CREATE TEMP TABLE _res_land_accts AS SELECT DISTINCT acct FROM land WHERE use_cd IN ({placeholders_land})", tuple(RESIDENTIAL_LAND_USE_CODES))
                    cur.execute('CREATE INDEX IF NOT EXISTS idx__res_land_accts_acct ON _res_land_accts(acct)')
                    land_clause = " AND acct IN (SELECT acct FROM _res_land_accts)"
                except Exception as e:
                    print(f"⚠️  Land use filtering setup failed: {e}")
                    land_clause = ''
            # Build parameter list dynamically for existing whitelist members actually present
            placeholders = ",".join(["?"] * len(RESIDENTIAL_STATE_CLASSES))
            # Delete rows failing state_class whitelist OR (when land available) not in residential land accounts
            if land_clause:
                cur.execute(f"DELETE FROM real_acct WHERE (state_class NOT IN ({placeholders}) OR acct NOT IN (SELECT acct FROM _res_land_accts))", tuple(RESIDENTIAL_STATE_CLASSES))
            else:
                cur.execute(f"DELETE FROM real_acct WHERE state_class NOT IN ({placeholders})", tuple(RESIDENTIAL_STATE_CLASSES))
            removed = cur.rowcount
            # Cascade delete orphan rows in related tables
            related_tables = ['building_res','fixtures','extra_features','owners','property_derived','property_geo']
            for t in related_tables:
                try:
                    cur.execute(f"DELETE FROM {t} WHERE acct NOT IN (SELECT acct FROM real_acct)")
                except Exception:
                    pass
            conn.commit()
            if land_clause:
                print(f"🏠  Residential + land-use filter applied: removed {removed:,} accounts.")
            else:
                print(f"🏠  Residential (state_class only) filter applied: removed {removed:,} accounts.")
        except Exception as e:
            print(f"⚠️  Residential pruning issue: {e}")

    # Create indexes & normalize acct values
    try:
        conn = get_connection(str(DB_PATH))
        cursor = wrap_cursor(conn)
        prune_to_residential(conn)
        print("🔍 Creating database indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_real_acct_acct ON real_acct(acct)",
            "CREATE INDEX IF NOT EXISTS idx_building_res_acct ON building_res(acct)",
            "CREATE INDEX IF NOT EXISTS idx_property_derived_acct ON property_derived(acct)",
            "CREATE INDEX IF NOT EXISTS idx_real_acct_addr ON real_acct(site_addr_1)",
            "CREATE INDEX IF NOT EXISTS idx_real_acct_zip ON real_acct(site_addr_3)",
        ]
        for index_sql in indexes:
            cursor.execute(index_sql)
        conn.commit(); conn.close()
        # Normalize acct whitespace
        try:
            conn = get_connection(str(DB_PATH))
            cur = wrap_cursor(conn)
            for t in ['real_acct','building_res','fixtures','structural_elem1','structural_elem2','extra_features','building_other','owners','property_derived','property_geo']:
                try:
                    cur.execute(f"PRAGMA table_info({t})")
                    cols = cur.fetchall()
                    if any(c[1].lower()=='acct' for c in cols):
                        cur.execute(f"UPDATE {t} SET acct = TRIM(acct) WHERE acct IS NOT NULL")
                except Exception:
                    pass
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            try: conn.close()
            except Exception: pass

        # Persist PPSF metric into property_derived
        ensure_ppsf_metric()
        print("✅ All data imported successfully (via extract_data)! Accounts normalized & PPSF metric updated")
        return True
    except Exception as e:
        print(f"❌ Error creating indexes after import: {e}")
        try:
            conn.rollback(); conn.close()
        except Exception:
            pass
        return False

# ----------------------------- Value Metrics Helper -----------------------------
def ensure_ppsf_metric():
    """Ensure persistent price-per-square-foot metric in property_derived.

    Adds ppsf column if missing; populates from tot_mkt_val / im_sq_ft (numeric, >0)."""
    if not DB_PATH.exists() and not USING_POSTGRES:
        return
    try:
        conn = get_connection(str(DB_PATH))
        cur = wrap_cursor(conn)
        if USING_POSTGRES:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='property_derived'")
            if cur.fetchone()[0] == 0:
                return
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_derived'")
            if cur.fetchone() is None:
                return
        if USING_POSTGRES:
            # Postgres: use information_schema to detect column; add if missing
            cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='property_derived'""")
            cols = [r[0].lower() for r in cur.fetchall()]
            if 'ppsf' not in cols:
                try:
                    cur.execute("ALTER TABLE property_derived ADD COLUMN IF NOT EXISTS ppsf DOUBLE PRECISION")
                except Exception as e:
                    print(f"⚠️  Could not add ppsf column (pg): {e}")
                    conn.commit(); return
        else:
            cur.execute("PRAGMA table_info(property_derived)")
            cols = [c[1].lower() for c in cur.fetchall()]
            if 'ppsf' not in cols:
                try:
                    cur.execute("ALTER TABLE property_derived ADD COLUMN ppsf REAL")
                except Exception as e:
                    print(f"⚠️  Could not add ppsf column: {e}")
                    conn.commit(); return
        # Refresh values (safe overwrite)
        cur.execute("""
            UPDATE property_derived
            SET ppsf = (
                SELECT CASE WHEN br.im_sq_ft IS NOT NULL AND br.im_sq_ft != '' AND br.im_sq_ft != '0'
                                AND ra.tot_mkt_val IS NOT NULL AND ra.tot_mkt_val != '' AND ra.tot_mkt_val != '0'
                             THEN CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)
                             ELSE NULL END
                FROM real_acct ra LEFT JOIN building_res br ON ra.acct = br.acct
                WHERE ra.acct = property_derived.acct)
        """)
        conn.commit()
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_property_derived_ppsf ON property_derived(ppsf)")
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️  PPSF metric update issue: {e}")
    finally:
        try:
            cur.close(); conn.close()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description='Import tax data into SQLite')
    parser.add_argument('--force', action='store_true', help='Force full re-import even if hashes match (ignores hash check)')
    parser.add_argument('--drop-db', action='store_true', help='Delete existing database file before import (implies --force)')
    args = parser.parse_args()

    print("🗃️  Harris County Tax Data SQLite Importer")
    print("=" * 50)
    if args.drop_db and DB_PATH.exists() and not USING_POSTGRES:
        try:
            DB_PATH.unlink()
            print(f"🗑️  Deleted existing database: {DB_PATH}")
        except Exception as e:
            print(f"❌ Failed to delete existing database: {e}")
    
    # Check for required files
    required_files = [
        TEXT_FILES_DIR / "real_acct.txt",
        TEXT_FILES_DIR / "building_res.txt",
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    if missing_files:
        print("❌ Missing required files:")
        for f in missing_files:
            print(f"   {f.name}")
        print("\n   Run step2_extract.py first to extract the data files.")
        return
    
    # Calculate combined hash of key files for change detection
    key_files = [
        TEXT_FILES_DIR / "real_acct.txt",
        TEXT_FILES_DIR / "building_res.txt",
        TEXT_FILES_DIR / "fixtures.txt",
        TEXT_FILES_DIR / "extra_features.txt",
    ]
    
    combined_hash_data = ""
    existing_files = []
    
    for file_path in key_files:
        if file_path.exists():
            file_hash = calculate_file_hash(file_path)
            combined_hash_data += file_hash
            existing_files.append(file_path.name)
    
    current_combined_hash = hashlib.sha256(combined_hash_data.encode()).hexdigest()
    
    # Load existing hashes
    existing_hashes = {} if (args.force or args.drop_db) else load_existing_hashes()
    
    # Check if import is needed
    should_import = True
    if args.force or args.drop_db:
        print("⚠️  Force flag set: ignoring hash comparison; full re-import will run.")
    else:
        if "combined_hash" in existing_hashes and existing_hashes["combined_hash"] == current_combined_hash:
            if DB_PATH.exists() or USING_POSTGRES:
                print("⏭️  Database up to date (file hashes match)")
                print(f"   Database: {DB_PATH}")
                # Show database stats
                conn = get_connection(str(DB_PATH))
                cursor = wrap_cursor(conn)
                try:
                    cursor.execute("SELECT COUNT(*) FROM real_acct")
                    acct_count = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM property_derived WHERE amenities IS NOT NULL")
                    amenities_count = cursor.fetchone()[0]
                    print(f"   Properties: {acct_count:,}")
                    print(f"   With amenities: {amenities_count:,}")
                    should_import = False
                except sqlite3.OperationalError:
                    print("   Database exists but seems incomplete, will re-import")
                finally:
                    conn.close()
            else:  # SQLite path only
                print("🔄 Database file missing, will import...")
        else:
            print("🔄 Data files changed, importing...")
    
    import_changed = False
    if should_import:
        print(f"\n📁 Importing from files: {', '.join(existing_files)}")
        
        if import_data_to_sqlite():
            # After the main import, load geographic centroids from parcels.csv produced in step2
            ensure_property_geo(force=args.force or args.drop_db)
            verify_database_integrity()

            # Save new hash (unless forced import requested yet we still update with new state)
            try:
                new_hashes = {"combined_hash": current_combined_hash}
                save_hashes(new_hashes)
            except Exception as e:
                print(f"⚠️  Could not save hash file: {e}")
            
            # Show final stats
            conn = get_connection(str(DB_PATH))
            cursor = wrap_cursor(conn)
            try:
                cursor.execute("SELECT COUNT(*) FROM real_acct")
                acct_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM property_derived WHERE amenities IS NOT NULL")
                amenities_count = cursor.fetchone()[0]
                print(f"\n📊 Import Summary:")
                print(f"  Total properties: {acct_count:,}")
                print(f"  Properties with amenities: {amenities_count:,}")
                print(f"  Database: {DB_PATH}")
                print(f"\n✅ Ready to run Flask app! Use: python app.py")
                import_changed = True
            finally:
                conn.close()
        else:
            print("❌ Import failed")
    else:
        # Even if skipping main import, still ensure geo + integrity
        ensure_property_geo(force=False)
        verify_database_integrity()
        print(f"\n✅ Database ready! Use: python app.py")

    # Emit JSON summary for orchestrator
    try:
        db_stats = {}
        if DB_PATH.exists() or USING_POSTGRES:
            try:
                conn = get_connection(str(DB_PATH))
                cur = wrap_cursor(conn)
                try:
                    cur.execute("SELECT COUNT(*) FROM real_acct")
                    db_stats['real_acct'] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute("SELECT COUNT(*) FROM property_derived")
                    db_stats['property_derived'] = cur.fetchone()[0]
                except Exception:
                    pass
            finally:
                try: cur.close(); conn.close()
                except Exception: pass
        summary = {
            'timestamp_utc': datetime.utcnow().isoformat() + 'Z',
            'should_import': should_import,
            'import_changed': import_changed,
            'database_exists': (DB_PATH.exists() or USING_POSTGRES),
            'db_stats': db_stats,
        }
        with open(SUMMARY_FILE, 'w') as f:
            json.dump(summary, f, indent=2)
    except Exception:
        pass

if __name__ == "__main__":
    main()
