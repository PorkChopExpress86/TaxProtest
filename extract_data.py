import pandas as pd
import os
import csv
import math
import sqlite3  # kept for specific OperationalError catches (SQLite path)
import os as _os
from db import get_connection, wrap_cursor
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import time
from contextlib import contextmanager

# Import refactored comparables modules
from taxprotest_site.comparables.services import find_comps
# Note: export_comparables removed to avoid circular import with views.py

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEXT_DIR = BASE_DIR / "text_files"
EXPORTS_DIR = BASE_DIR / "Exports"
EXPORTS_DIR.mkdir(exist_ok=True)

EXTRACTED_DIR = BASE_DIR / "extracted"

DB_PATH = BASE_DIR / 'data' / 'database.sqlite'
USING_POSTGRES = _os.getenv("TAXPROTEST_DATABASE_URL", "").startswith("postgres")
PROFILE_LOAD = _os.getenv("TAXPROTEST_PROFILE_LOAD", "0").lower() in {"1","true","yes"}
POSTGIS_ENABLED = bool(int(_os.getenv("TAXPROTEST_POSTGIS_FORCE", "0")))  # manual override; auto-detect later

# Cross-platform default file encoding and simple detector
DEFAULT_ENCODING = 'mbcs' if os.name == 'nt' else 'utf-8'

def detect_text_encoding(path: Path, default: str = DEFAULT_ENCODING) -> str:
    """Best-effort tiny detector for common encodings in exported text files.

    Prefers BOM-aware UTFs; falls back to utf-8, then cp1252. Keeps default on success.
    """
    try:
        with open(path, 'rb') as bf:
            head = bf.read(4)
        # UTF BOMs
        if head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff"):
            return 'utf-16'
        if head.startswith(b"\xef\xbb\xbf"):
            return 'utf-8-sig'
        # Try utf-8 fast path
        try:
            with open(path, 'r', encoding='utf-8') as tf:
                for _ in range(3):
                    if not tf.readline():
                        break
            return 'utf-8'
        except UnicodeDecodeError:
            pass
        # Try Windows-1252 (common on Windows exports)
        try:
            with open(path, 'r', encoding='cp1252') as tf:
                for _ in range(3):
                    if not tf.readline():
                        break
            return 'cp1252'
        except UnicodeDecodeError:
            pass
    except Exception:
        pass
    return default

@contextmanager
def profile(label: str):
    if not PROFILE_LOAD:
        yield; return
    start = time.perf_counter()
    try:
        yield
    finally:
        dur = time.perf_counter() - start
        print(f"⏱️  {label} {dur:.2f}s")

def _table_exists(cur, name: str) -> bool:
    if USING_POSTGRES:
        try:
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1", (name.lower(),))
            return cur.fetchone() is not None
        except Exception:
            return False
    else:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None


def create_table_from_csv(cursor, table_name: str, csv_path: Path, encoding: str = DEFAULT_ENCODING):
    """Create table schema by reading first few rows of CSV"""
    try:
        # Decide on encoding for this file
        enc = detect_text_encoding(csv_path, encoding)
        with open(csv_path, 'r', encoding=enc, errors='ignore', newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            headers = next(reader)

        # Clean column names -> safe, lowercase SQL identifiers (unquoted)
        clean_headers = []
        seen = set()
        for h in headers:
            # replace non-alnum with underscore and lowercase
            base = ''.join(c if c.isalnum() else '_' for c in h)
            base = base.strip('_').lower() or 'col'
            if base and not base[0].isalpha():
                base = f"c_{base}"
            name = base
            i = 1
            while name in seen:
                name = f"{base}_{i}"
                i += 1
            seen.add(name)
            clean_headers.append(name)

        # Create table with TEXT columns (SQLite flexible, Postgres text OK)
        columns = ', '.join(f'{h} TEXT' for h in clean_headers)
        cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
        cursor.execute(f'CREATE TABLE {table_name} ({columns})')

        return clean_headers
    except (UnicodeDecodeError, LookupError):
        if encoding != 'utf-8':
            return create_table_from_csv(cursor, table_name, csv_path, encoding='utf-8')
        raise


def load_csv_to_table(cursor, table_name: str, csv_path: Path, headers: list, encoding: str = DEFAULT_ENCODING, batch_size=10000):
    """Load CSV data into SQLite table in batches using pandas for robustness."""
    try:
        # Resolve encoding cross-platform
        enc = detect_text_encoding(csv_path, encoding)
        # Use pandas to read the tab-separated file, treat all columns as strings to avoid type errors
        try:
            df = pd.read_csv(csv_path, sep='\t', header=0, names=headers, encoding=enc, on_bad_lines='warn', low_memory=False, dtype=str)
        except UnicodeDecodeError:
            for alt in ('cp1252','utf-8-sig','latin-1'):
                try:
                    df = pd.read_csv(csv_path, sep='\t', header=0, names=headers, encoding=alt, on_bad_lines='warn', low_memory=False, dtype=str)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Last resort: ignore errors to keep loading
                df = pd.read_csv(csv_path, sep='\t', header=0, names=headers, encoding='utf-8', on_bad_lines='skip', low_memory=False, dtype=str, engine='python', quoting=3)

        # Clean up column names if they were not provided
        df.columns = [(''.join(c if c.isalnum() else '_' for c in h)) for h in df.columns]

        # Trim whitespace from all string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].str.strip()

        # Write the data to the SQLite table
        df.to_sql(table_name, cursor.connection, if_exists='replace', index=False, chunksize=batch_size)
        print(f"  inserted {len(df)} rows into {table_name}")

    except (UnicodeDecodeError, LookupError):
        if encoding != 'utf-8':
            load_csv_to_table(cursor, table_name, csv_path, headers, encoding='utf-8', batch_size=batch_size)
        else:
            raise
    except Exception as e:
        print(f"  Could not load {csv_path} into {table_name} using pandas. Error: {e}")
        # Fallback to original implementation if pandas fails
        _load_csv_to_table_original(cursor, table_name, csv_path, headers, encoding, batch_size)

def _load_csv_to_table_original(cursor, table_name: str, csv_path: Path, headers: list, encoding: str = DEFAULT_ENCODING, batch_size=10000):
    """Original implementation for loading CSV data into SQLite table in batches"""
    # Increase CSV field size limit
    try:
        csv.field_size_limit(10_000_000)
    except Exception:
        pass
    
    try:
        enc = detect_text_encoding(csv_path, encoding)
        with open(csv_path, 'r', encoding=enc, errors='ignore', newline='') as f:
            next(f)  # Skip header row
            
            batch = []
            for row_num, line in enumerate(f, 1):
                parts = line.rstrip('\n').split('\t')
                normalized_row = parts[:len(headers)] + [''] * (len(headers) - len(parts))
                acct_indices = [i for i, h in enumerate(headers) if h.lower() == 'acct']
                if acct_indices:
                    ai = acct_indices[0]
                    try:
                        normalized_row[ai] = normalized_row[ai].strip()
                    except Exception:
                        pass
                batch.append(normalized_row)
                
                if len(batch) >= batch_size:
                    placeholders = ', '.join(['?' for _ in headers])
                    cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                    print(f"  inserted batch ending at row {row_num}")
                    batch = []
            
            if batch:
                placeholders = ', '.join(['?' for _ in headers])
                cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                print(f"  inserted final batch of {len(batch)} rows")
                acct_indices = [i for i, h in enumerate(headers) if h.lower() == 'acct']
                if acct_indices:
                    try:
                        cursor.execute(f"UPDATE {table_name} SET acct = TRIM(acct) WHERE acct IS NOT NULL")
                    except Exception:
                        pass
                
    except (UnicodeDecodeError, LookupError):
        if encoding != 'utf-8':
            _load_csv_to_table_original(cursor, table_name, csv_path, headers, encoding='utf-8', batch_size=batch_size)
        else:
            raise


def load_data_to_sqlite():
    files = {
        "building_res": TEXT_DIR / "building_res.txt",
        "real_acct": TEXT_DIR / "real_acct.txt",
        # Note: land.txt doesn't seem to be extracted, so we'll skip it for now
    }
    conn = get_connection(str(DB_PATH))
    cursor = wrap_cursor(conn)
    try:
        for table, path in files.items():
            if not path.exists():
                print(f"Skip {table}: file not found at {path}")
                continue
            print(f"Loading {table} from {path} ...")
            with profile(f"core {table}"):
                headers = create_table_from_csv(cursor, table, path)
            if USING_POSTGRES:
                # Simple COPY fast path (tab separated). If it fails, fall back to pandas loader.
                try:
                    raw_cur = conn.cursor()
                    copy_cols = ', '.join(headers)
                    if hasattr(raw_cur, 'copy'):
                        import csv as _csv
                        try:
                            _csv.field_size_limit(10_000_000)
                        except Exception:
                            pass
                        enc = detect_text_encoding(path)
                        with open(path, 'r', encoding=enc, errors='ignore') as f:
                            f.readline()  # skip header
                            copy_cmd = f"COPY {table} ({copy_cols}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', NULL '', HEADER false)"
                            try:
                                with raw_cur.copy(copy_cmd) as cp:  # type: ignore[attr-defined]
                                    for line in f:
                                        parts = line.rstrip('\n').split('\t')
                                        row2 = parts[:len(headers)] + [''] * (len(headers) - len(parts))
                                        row2 = [c.strip() if isinstance(c, str) else c for c in row2]
                                        cp.write_row(row2)
                            except Exception as stream_e:
                                print(f"  ⚠️  Streaming COPY failed ({stream_e}); retrying with larger field size and strict row writer.")
                                f.seek(0); f.readline()
                                with raw_cur.copy(copy_cmd) as cp:
                                    for line in f:
                                        parts = line.rstrip('\n').split('\t')
                                        row2 = parts[:len(headers)] + [''] * (len(headers) - len(parts))
                                        row2 = [c.strip() if isinstance(c, str) else c for c in row2]
                                        cp.write_row(row2)
                    else:
                        # No psycopg copy API available; force fallback loader
                        raise RuntimeError("psycopg copy API not available")
                    conn.commit()
                    print(f"  (COPY) inserted rows into {table}")
                    continue
                except Exception as pg_e:
                    try: conn.rollback()
                    except Exception: pass
                    print(f"  ⚠️  COPY fast path failed for {table}: {pg_e}; falling back to standard load.")
            # Fallback / SQLite path
            load_csv_to_table(cursor, table, path, headers)
        conn.commit(); print("All available files loaded.")

        # Owners
        owners_path = TEXT_DIR / 'owners.txt'
        if owners_path.exists():
            print("Loading owners ...")
            cursor.execute("DROP TABLE IF EXISTS owners")
            cursor.execute("CREATE TABLE owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
            loaded_copy = False
            if USING_POSTGRES:
                with profile("owners COPY"):
                    try:
                        raw_cur = conn.cursor()
                        if hasattr(raw_cur,'copy'):
                            copy_cmd = "COPY owners (acct, ln_num, name, aka, pct_own) FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', NULL '', HEADER false)"
                            import csv as _csv, io
                            enc_own = detect_text_encoding(owners_path)
                            with open(owners_path,'r',encoding=enc_own,errors='ignore') as f:
                                f.readline()
                                try:
                                    with raw_cur.copy(copy_cmd) as cp:  # type: ignore[attr-defined]
                                        rdr=_csv.reader(f, delimiter='\t')
                                        for row in rdr:
                                            row2=row[:5]+['']*(5-len(row)); row2=[c.strip() for c in row2]
                                            cp.write_row(row2)
                                except Exception as stre:
                                    print(f"  ⚠️ streaming owners COPY failed ({stre}); buffering.")
                                    f.seek(0); f.readline(); buf=io.StringIO(); w=_csv.writer(buf, delimiter='\t', lineterminator='\n')
                                    for line in f:
                                        parts=line.rstrip('\n').split('\t'); parts+=['']*(5-len(parts))
                                        w.writerow([p.strip() for p in parts[:5]])
                                    buf.seek(0); raw_cur.execute(copy_cmd, buf.read())
                            conn.commit(); loaded_copy=True; print("  (COPY) owners loaded")
                    except Exception as pg_e:
                        try: conn.rollback()
                        except Exception: pass
                        print(f"  ⚠️ owners COPY failed: {pg_e}; fallback to batch inserts")
            if not loaded_copy:
                with profile("owners batch"):
                    with open(owners_path,'r',encoding='utf-8',errors='ignore') as f:
                        f.readline(); batch=[]
                        for line in f:
                            parts=line.rstrip('\n').split('\t'); parts+=['']*(5-len(parts))
                            batch.append(tuple(p.strip() for p in parts[:5]))
                            if len(batch)>=10000:
                                cursor.executemany('INSERT INTO owners VALUES (?,?,?,?,?)', batch); batch.clear()
                        if batch: cursor.executemany('INSERT INTO owners VALUES (?,?,?,?,?)', batch)
                conn.commit()
        else:
            cursor.execute("CREATE TABLE IF NOT EXISTS owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
            conn.commit()

        # Descriptors helper (original simple loader retained; no COPY optimization yet)
        def load_descriptor(filename, table):
            for base in (TEXT_DIR, EXTRACTED_DIR):
                p = base/filename
                if p.exists():
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        cursor.execute(f"CREATE TABLE {table} (col1 TEXT, col2 TEXT, col3 TEXT, col4 TEXT, col5 TEXT)")
                        with open(p,'r',encoding='utf-8',errors='ignore') as f:
                            f.readline(); batch=[]
                            for line in f:
                                parts=line.rstrip('\n').split('\t'); parts+=['']*(5-len(parts))
                                batch.append(tuple(pp.strip() for pp in parts[:5]))
                                if len(batch)>=5000:
                                    cursor.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?)", batch); batch.clear()
                            if batch:
                                cursor.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?)", batch)
                        conn.commit(); print(f"Loaded descriptor {filename}")
                    except Exception as e:
                        print(f"Descriptor load failed {filename}: {e}")
                    break

        # Supplemental tables (fixtures, building_other, etc.) COPY optimization
        supplemental = {}
        for fname in ['fixtures.txt','building_other.txt','structural_elem1.txt','structural_elem2.txt','extra_features.txt']:
            for base in [TEXT_DIR, EXTRACTED_DIR]:
                p = base/fname
                if p.exists(): supplemental[fname]=p; break
        for fname, path in supplemental.items():
            tname=fname.replace('.txt','').replace('-','_')
            print(f"Loading supplemental {tname} ...")
            hdrs = create_table_from_csv(cursor, tname, path)
            loaded_copy=False
            if USING_POSTGRES:
                with profile(f"supp {tname} COPY"):
                    try:
                        raw_cur=conn.cursor(); cols=', '.join(hdrs)
                        if hasattr(raw_cur,'copy'):
                            import csv as _csv, io
                            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                                f.readline(); copy_cmd=f"COPY {tname} ({cols}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', NULL '', HEADER false)"
                                try:
                                    with raw_cur.copy(copy_cmd) as cp:  # type: ignore[attr-defined]
                                        rdr=_csv.reader(f, delimiter='\t')
                                        for row in rdr:
                                            row2=row[:len(hdrs)]+['']*(len(hdrs)-len(row)); row2=[c.strip() for c in row2]
                                            cp.write_row(row2)
                                    conn.commit(); loaded_copy=True; print(f"  (COPY) {tname} loaded")
                                except Exception as se:
                                    print(f"  ⚠️ streaming {tname} COPY failed ({se}); buffering.")
                                    f.seek(0); f.readline(); buf=io.StringIO(); w=_csv.writer(buf, delimiter='\t', lineterminator='\n')
                                    for line in f:
                                        parts=line.rstrip('\n').split('\t'); parts+=['']*(len(hdrs)-len(parts))
                                        w.writerow([p.strip() for p in parts[:len(hdrs)]])
                                    buf.seek(0); raw_cur.execute(copy_cmd, buf.read()); conn.commit(); loaded_copy=True; print(f"  (COPY) {tname} loaded")
                    except Exception as pg_e:
                        try: conn.rollback()
                        except Exception: pass
                        print(f"  ⚠️ {tname} COPY failed: {pg_e}; fallback")
            if not loaded_copy:
                with profile(f"supp {tname} batch"):
                    load_csv_to_table(cursor, tname, path, hdrs, batch_size=5000)
        # Quality ranking
        quality_rank={}
        try:
            cursor.execute("SELECT col1,col2 FROM quality_code_desc WHERE col1<>'' AND col2<>''")
            for c1,c2 in cursor.fetchall():
                # simple heuristic mapping
                base=c1.strip()[:1]
                mapping={'X':10,'A':9,'B':7,'C':5,'D':3,'E':1.5,'F':1}
                if base in mapping: quality_rank[c1.strip()]=mapping[base]
        except Exception:
            try:
                cursor.connection.rollback()
            except Exception:
                pass
        if not quality_rank:
            quality_rank={'X':10,'A':9,'B':7,'C':5,'D':3,'E':1.5,'F':1}

        # Land use mapping
        land_use_map={}
        try:
            cursor.execute("SELECT col1,col2 FROM land_use_code_desc WHERE col1<>''")
            land_use_map={r[0].strip():r[1].strip() for r in cursor.fetchall() if r[0]}
        except Exception:
            try:
                cursor.connection.rollback()
            except Exception:
                pass
        fallback_types={'A1':'Residential Single-Family','A2':'Residential Multi-Family','B2':'Commercial','B3':'Industrial','X3':'Exempt'}
        for k,v in fallback_types.items(): land_use_map.setdefault(k,v)

        # Regex patterns
        bed_patterns=[re.compile(r'\b(\d{1,2})\s*(?:BR|BED|BEDROOM)S?\b',re.IGNORECASE), re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})'), re.compile(r'\b(\d{1,2})\s*BED\b',re.IGNORECASE)]
        bath_patterns=[re.compile(r'\b(\d{1,2}(?:\.\d)?)\s*(?:BA|BATH|BATHROOM)S?\b',re.IGNORECASE)]

        # Base building rows
        cursor.execute("SELECT acct, dscr, structure_dscr, eff, qa_cd, property_use_cd, im_sq_ft, gross_ar FROM building_res")
        building_data={r[0]:r[1:] for r in cursor.fetchall()}

        # Fixtures counts (bed/bath + stories)
        fixture_counts={}
        try:
            cursor.execute("SELECT acct, type, type_dscr, units FROM fixtures WHERE type IS NOT NULL AND units IS NOT NULL")
            for acct, ftype, tdesc, units in cursor.fetchall():
                at=acct.strip(); fc=fixture_counts.setdefault(at,{'bedrooms':0,'bathrooms':0.0,'stories':None,'c_stories':None})
                try: u=float(units) if units not in (None,'') else 0
                except: u=0
                fupper=(ftype or '').upper(); dupper=(tdesc or '').upper()
                if fupper=='RMB' or 'BEDROOM' in dupper: fc['bedrooms']+=int(u)
                if fupper.startswith('AP') and 'BEDROOM' in dupper:
                    mult={'AP1':1,'AP2':2,'AP3':3,'AP4':4}.get(fupper,0); fc['bedrooms']+=int(u)*mult
                if fupper=='RMF' or 'FULL BATH' in dupper: fc['bathrooms']+=u
                elif fupper=='RMH' or 'HALF BATH' in dupper: fc['bathrooms']+=0.5*u
                if fupper=='STY' and u>0 and fc.get('stories') is None:
                    try: fc['stories']=int(round(u))
                    except: pass
                if fupper=='STC' and u>0 and fc.get('c_stories') is None:
                    try: fc['c_stories']=int(round(u))
                    except: pass
        except Exception:
            pass

        # Amenities
        amenities_data={}
        try:
            cursor.execute("SELECT acct, l_dscr FROM extra_features WHERE l_dscr IS NOT NULL")
            for acct, desc in cursor.fetchall():
                if desc:
                    up=desc.upper()
                    if any(k in up for k in ['POOL','GARAGE','DECK','PATIO','FIRE','SPA']):
                        amenities_data.setdefault(acct.strip(),[]).append(desc.strip())
        except Exception:
            pass

        # Derive metrics (stories primary from fixtures)
        rows=[]; now_year=datetime.now().year
        for acct,(dscr, sd, eff, qa_cd, puc, im_sq_ft, gross_ar) in building_data.items():
            at=acct.strip(); fc=fixture_counts.get(at,{})
            beds=fc.get('bedrooms'); baths=fc.get('bathrooms')
            stories=fc.get('stories') if fc.get('stories') is not None else fc.get('c_stories')
            # Heuristic backup using gross area ratio if still None
            if stories is None:
                try:
                    if im_sq_ft and gross_ar and im_sq_ft not in ('','0') and gross_ar not in ('','0'):
                        ratio=float(gross_ar)/float(im_sq_ft)
                        if 1.0 <= ratio <= 4.0:
                            stories=int(round(ratio))
                except: pass
            qa=(qa_cd or '').strip()
            q_rating=quality_rank.get(qa)
            age_score=None
            if eff and str(eff).isdigit():
                try:
                    age=max(0, now_year-int(eff)); age_score=max(1.0, min(10.0, 10-age*0.05))
                except: pass
            overall=None
            if q_rating is not None and age_score is not None: overall=round(q_rating*0.7+age_score*0.3,1)
            elif q_rating is not None: overall=q_rating
            elif age_score is not None: overall=age_score
            ptype=land_use_map.get(puc)
            expl=None
            if overall is not None:
                parts=[]
                if q_rating is not None: parts.append(f"quality {qa or 'NA'} ({q_rating}/10)")
                if age_score is not None and eff: parts.append(f"age ({eff}, {age_score:.1f}/10)")
                expl=("Score: "+', '.join(parts))[:180]
            amenities=None; has_pool=0; has_garage=0
            if at in amenities_data:
                al=amenities_data[at][:5]
                amenities=', '.join(al) if al else None
                upc=' '.join(al).upper()
                if 'POOL' in upc: has_pool=1
                if 'GARAGE' in upc and 'NO GARAGE' not in upc: has_garage=1
            if has_garage==0 and (dscr or sd):
                desc_combo=(' '.join(filter(None,[dscr,sd]))).upper()
                if 'GARAGE' in desc_combo and 'NO GARAGE' not in desc_combo:
                    has_garage=1
            if has_pool==0 and (dscr or sd) and 'POOL' in (' '.join(filter(None,[dscr,sd]))).upper():
                has_pool=1
            rows.append((acct, beds, baths, ptype, qa, q_rating, overall, expl, amenities, stories, has_pool, has_garage))

        if rows:
            try:
                cursor.execute("DROP TABLE IF EXISTS property_derived")
                cursor.execute("""
                    CREATE TABLE property_derived (
                        acct TEXT,
                        bedrooms TEXT,
                        bathrooms TEXT,
                        property_type TEXT,
                        quality_code TEXT,
                        quality_rating REAL,
                        overall_rating REAL,
                        rating_explanation TEXT,
                        amenities TEXT,
                        stories INTEGER,
                        has_pool INTEGER,
                        has_garage INTEGER
                    )
                """)
            except Exception:
                try:
                    cursor.connection.rollback()
                except Exception:
                    pass
            cursor.executemany(
                """
                INSERT INTO property_derived (
                    acct, bedrooms, bathrooms, property_type, quality_code,
                    quality_rating, overall_rating, rating_explanation, amenities,
                    stories, has_pool, has_garage
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            conn.commit(); print(f"Inserted {len(rows)} derived property rows.")
        else:
            print("No derived property metrics generated.")
    finally:
        conn.close()


def search_properties(account: str = "", street: str = "", zip_code: str = "", owner: str = "", exact_match: bool = False) -> List[Dict]:
    """Search for properties with safe fallback columns.

    The original implementation referenced bedroom/bathroom/rating columns that
    are not present in the current building_res dataset. We project NULLs for
    those optional semantic fields so the template logic (which checks truthy
    values) still works and displays 'N/A'.
    """
    where_clauses = []
    params: List[str] = []
    if account:
        where_clauses.append("CAST(ra.acct AS TEXT) LIKE ?")
        params.append(f"%{account.strip()}%")
    if street:
        street_clean = street.strip().upper()
        if exact_match:
            where_clauses.append("UPPER(ra.site_addr_1) = ?")
            params.append(street_clean)
        else:
            where_clauses.append("UPPER(ra.site_addr_1) LIKE ?")
            params.append(f"%{street_clean}%")
    if zip_code:
        where_clauses.append("ra.site_addr_3 LIKE ?")
        params.append(f"%{zip_code.strip()}%")
    if owner:
        # Use owners table (loaded from owners.txt) when present; fallback to mailto otherwise at query time
        where_clauses.append("( (ow.name IS NOT NULL AND UPPER(ow.name) LIKE ?) OR (ow.name IS NULL AND UPPER(ra.mailto) LIKE ?) )")
        o = owner.strip().upper()
        params.extend([f"%{o}%", f"%{o}%"])    
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    # Determine if property_geo table exists (coordinates optional)
    conn = get_connection(str(DB_PATH))
    cursor = wrap_cursor(conn)
    try:
        has_geo = _table_exists(cursor, 'property_geo')
    finally:
        cursor.close(); conn.close()

    geo_join = "LEFT JOIN property_geo pg ON ra.acct = pg.acct" if has_geo else ""
    geo_select = 'pg.latitude AS "Latitude", pg.longitude AS "Longitude"' if has_geo else 'NULL AS "Latitude", NULL AS "Longitude"'

    sql = f"""
    SELECT ra.site_addr_1 AS "Address",
         ra.site_addr_3 AS "Zip Code",
         br.eff AS "Build Year",
         pd.bedrooms AS "Bedrooms",
         pd.bathrooms AS "Bathrooms",
         pd.stories AS "Stories",
         br.im_sq_ft AS "Building Area",
         ra.land_val AS "Land Value",
         ra.bld_val AS "Building Value",
         CAST(ra.acct AS TEXT) AS "Account Number",
         ra.tot_mkt_val AS "Market Value",
         CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
             ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS "Price Per Sq Ft",
         ra.land_ar AS "Land Area",
         pd.property_type AS "Property Type",
         pd.amenities AS "Estimated Amenities",
        pd.overall_rating AS "Overall Rating",
        pd.quality_rating AS "Quality Rating",
        NULL AS "Value Rating",
        pd.rating_explanation AS "Rating Explanation",
        COALESCE(ow.name, ra.mailto) AS "Owner Name",
           {geo_select}
    FROM real_acct ra
    LEFT JOIN building_res br ON ra.acct = br.acct
    LEFT JOIN owners ow ON ra.acct = ow.acct
    LEFT JOIN property_derived pd ON ra.acct = pd.acct
    {geo_join}
    {where_sql}
    ORDER BY ra.site_addr_1 ASC
    LIMIT 100;"""
    conn = get_connection(str(DB_PATH))
    cursor = wrap_cursor(conn)
    try:
        try:
            cursor.execute(sql, params)
        except sqlite3.OperationalError as e:
            if 'no such table: owners' in str(e):
                cursor.execute("CREATE TABLE IF NOT EXISTS owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
                cursor.execute(sql, params)
            else:
                raise
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        out: List[Dict] = []
        for r in rows:
            rec = dict(zip(cols, r))
            # Provide legacy/simple keys expected by templates
            rec['acct'] = rec.get('Account Number')
            rec['owner_name'] = rec.get('Owner Name')
            rec['site_addr_1'] = rec.get('Address')
            rec['site_addr_3'] = rec.get('Zip Code')
            rec['bedrooms'] = rec.get('Bedrooms')
            rec['bathrooms'] = rec.get('Bathrooms')
            rec['stories'] = rec.get('Stories')
            rec['amenities'] = rec.get('Estimated Amenities') or rec.get('Amenities')
            rec['build_year'] = rec.get('Build Year')
            # Normalize valuation & size fields for easier template access
            rec['market_value'] = rec.get('Market Value')
            rec['land_value'] = rec.get('Land Value')
            rec['building_value'] = rec.get('Building Value')
            rec['land_area'] = rec.get('Land Area')
            rec['building_area'] = rec.get('Building Area')
            rec['property_type'] = rec.get('Property Type')
            rec['overall_rating'] = rec.get('Overall Rating')
            rec['quality_rating'] = rec.get('Quality Rating')
            rec['rating_explanation'] = rec.get('Rating Explanation')
            # Normalize price per square foot for template (ppsf) convenience
            ppsf_val = rec.get('Price Per Sq Ft')
            try:
                if ppsf_val is not None and ppsf_val != '' and ppsf_val != '0':
                    rec['ppsf'] = round(float(ppsf_val), 2)
                else:
                    rec['ppsf'] = None
            except Exception:
                rec['ppsf'] = None
            out.append(rec)
        return out
    finally:
        conn.close()

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def find_comparables(acct: str, max_distance_miles: float = 15.0, size_tolerance: float = 0.2, land_tolerance: float = 0.2, limit: int = 50) -> List[Dict]:
    conn = get_connection(str(DB_PATH))
    cur = wrap_cursor(conn)
    try:
        # Fast PostGIS path if geometry present
        if USING_POSTGRES:
            try:
                cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name='property_geo' AND column_name='geom'")
                if cur.fetchone():
                    # Get base property location & attributes
                    cur.execute("""
                        SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                               pd.bedrooms, pd.bathrooms, pg.geom, pd.overall_rating
                        FROM real_acct ra
                        LEFT JOIN building_res br ON ra.acct = br.acct
                        LEFT JOIN property_derived pd ON ra.acct = pd.acct
                        JOIN property_geo pg ON ra.acct = pg.acct
                        WHERE ra.acct = ? AND pg.geom IS NOT NULL
                    """, (acct,))
                    base = cur.fetchone()
                    if base:
                        (acct_b, addr, zipc, mval, land_ar, im_sq_ft, bedrooms, bathrooms, geom, rating) = base
                        # Distance in meters (PostGIS geography fallback via ST_DWithin on geometry approximated to planar for small radius)
                        meters = max_distance_miles * 1609.34
                        cur.execute("""
                            SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                                   pd.bedrooms, pd.bathrooms, ST_Distance(pg.geom, pg2.geom) AS dist_m,
                                   pd.overall_rating
                            FROM property_geo pg2
                            JOIN real_acct ra ON ra.acct = pg2.acct
                            LEFT JOIN building_res br ON ra.acct = br.acct
                            LEFT JOIN property_derived pd ON ra.acct = pd.acct
                            JOIN property_geo pg ON pg.acct = ?
                            WHERE pg2.geom IS NOT NULL AND pg2.acct <> ?
                              AND ST_DWithin(pg.geom, pg2.geom, ?)
                            LIMIT ?
                        """, (acct, acct, meters, limit*5))
                        candidates = cur.fetchall()
                        results: List[Dict] = []
                        for c in candidates:
                            (c_acct, c_addr, c_zip, c_mval, c_land, c_im, c_bed, c_bath, dist_m, c_rating) = c
                            # Simple filters mirrored from non-spatial path
                            try:
                                if im_sq_ft and c_im and im_sq_ft not in ('','0') and c_im not in ('','0') and size_tolerance:
                                    base_im = float(im_sq_ft); cimf=float(c_im)
                                    if not (base_im*(1-size_tolerance) <= cimf <= base_im*(1+size_tolerance)):
                                        continue
                            except Exception:
                                pass
                            try:
                                if land_ar and c_land and land_ar not in ('','0') and c_land not in ('','0') and land_tolerance:
                                    base_land=float(land_ar); cland=float(c_land)
                                    if not (base_land*(1-land_tolerance) <= cland <= base_land*(1+land_tolerance)):
                                        continue
                            except Exception:
                                pass
                            ppsf=None
                            try:
                                if c_im and c_mval and c_im not in ('','0'):
                                    ppsf=float(c_mval)/float(c_im)
                            except Exception:
                                pass
                            results.append({
                                'Account Number': c_acct,
                                'Address': c_addr,
                                'Zip Code': c_zip,
                                'Market Value': c_mval,
                                'Land Area': c_land,
                                'Building Area': c_im,
                                'Bedrooms': c_bed,
                                'Bathrooms': c_bath,
                                'Overall Rating': c_rating,
                                'Distance Miles': round(dist_m/1609.34,2) if dist_m is not None else None,
                                'Price Per Sq Ft': round(ppsf,2) if ppsf else None,
                            })
                        results.sort(key=lambda r: (r['Distance Miles'] or 0, r['Price Per Sq Ft'] or 0))
                        return results[:limit]
            except Exception:
                # Fall back to legacy method on any PostGIS error
                pass
        # Bail out early if geo table absent
        if not _table_exists(cur, 'property_geo'):
            return []  # No geo coordinates available yet
        # Base property with bedroom/bathroom data
        cur.execute("""SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                             pd.bedrooms, pd.bathrooms, pg.latitude, pg.longitude, pd.overall_rating
                      FROM real_acct ra
                      LEFT JOIN building_res br ON ra.acct = br.acct
                      LEFT JOIN property_derived pd ON ra.acct = pd.acct
                      LEFT JOIN property_geo pg ON ra.acct = pg.acct
                      WHERE ra.acct = ?""", (acct,))
        base = cur.fetchone()
        if not base:
            return []
        (acct, addr, zipc, mval, land_ar, im_sq_ft, bedrooms, bathrooms, blat, blon, rating) = base
        if blat is None or blon is None:
            return []
        # Normalized numeric baseline
        try:
            base_im = float(im_sq_ft) if im_sq_ft and im_sq_ft not in ('','0') else None
        except:
            base_im = None
        try:
            base_land = float(land_ar) if land_ar and land_ar not in ('','0') else None
        except:
            base_land = None
        im_min = (base_im * (1 - size_tolerance)) if base_im else None
        im_max = (base_im * (1 + size_tolerance)) if base_im else None
        land_min = (base_land * (1 - land_tolerance)) if base_land else None
        land_max = (base_land * (1 + land_tolerance)) if base_land else None
        deg_buffer = max_distance_miles / 69.0
        
        # Candidate comps within bounding box with bedroom/bathroom data
        cur.execute("""SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                             pd.bedrooms, pd.bathrooms, pg.latitude, pg.longitude, pd.overall_rating
                      FROM real_acct ra
                      LEFT JOIN building_res br ON ra.acct = br.acct
                      LEFT JOIN property_derived pd ON ra.acct = pd.acct
                      JOIN property_geo pg ON ra.acct = pg.acct
                      WHERE pg.latitude BETWEEN ? AND ? AND pg.longitude BETWEEN ? AND ? AND ra.acct <> ?""",
                    (blat - deg_buffer, blat + deg_buffer, blon - deg_buffer, blon + deg_buffer, acct))
        comps = []
        rows_raw = cur.fetchall()
        for row in rows_raw:
            (c_acct, c_addr, c_zip, c_mval, c_land, c_im, c_bed, c_bath, c_lat, c_lon, c_rating) = row
            if c_lat is None or c_lon is None:
                continue
            # Apply size filter only if both base and candidate sizes are known
            try:
                if base_im and c_im and c_im not in ('','0') and im_min is not None and im_max is not None:
                    cimf = float(c_im)
                    if cimf < im_min or cimf > im_max:
                        continue
            except: pass
            # Apply land filter only if both base and candidate land areas are known
            try:
                if base_land and c_land and c_land not in ('','0') and land_min is not None and land_max is not None:
                    clandf = float(c_land)
                    if clandf < land_min or clandf > land_max:
                        continue
            except: pass
            dist = haversine(float(blat), float(blon), float(c_lat), float(c_lon))
            if dist <= max_distance_miles:
                ppsf = None
                if c_im and c_mval and str(c_im) not in ('0',''):
                    try:
                        ppsf = float(c_mval)/float(c_im)
                    except Exception:
                        pass
                comps.append({
                    'Account Number': c_acct,
                    'Address': c_addr,
                    'Zip Code': c_zip,
                    'Market Value': c_mval,
                    'Land Area': c_land,
                    'Building Area': c_im,
                    'Bedrooms': c_bed,
                    'Bathrooms': c_bath,
                    'Overall Rating': c_rating,
                    'Latitude': c_lat,
                    'Longitude': c_lon,
                    'Distance Miles': round(dist, 2),
                    'Price Per Sq Ft': round(ppsf, 2) if ppsf else None
                })
        # If no comps found, progressively relax constraints: first distance, then size/land filters already implicitly relaxed when unknown
        if not comps:
            # Expand search radius iteratively (2x then 3x) up to 15 miles
            for factor in (2, 3):
                new_radius = max_distance_miles * factor
                deg_buffer2 = new_radius / 69.0
                cur.execute("""SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                                     pd.bedrooms, pd.bathrooms, pg.latitude, pg.longitude, pd.overall_rating
                              FROM real_acct ra
                              LEFT JOIN building_res br ON ra.acct = br.acct
                              LEFT JOIN property_derived pd ON ra.acct = pd.acct
                              JOIN property_geo pg ON ra.acct = pg.acct
                              WHERE pg.latitude BETWEEN ? AND ? AND pg.longitude BETWEEN ? AND ? AND ra.acct <> ?""",
                            (blat - deg_buffer2, blat + deg_buffer2, blon - deg_buffer2, blon + deg_buffer2, acct))
                rows2 = cur.fetchall()
                for row in rows2:
                    (c_acct, c_addr, c_zip, c_mval, c_land, c_im, c_bed, c_bath, c_lat, c_lon, c_rating) = row
                    if c_lat is None or c_lon is None:
                        continue
                    dist = haversine(float(blat), float(blon), float(c_lat), float(c_lon))
                    if dist <= new_radius:
                        ppsf = None
                        if c_im and c_mval and str(c_im) not in ('0',''):
                            try: ppsf = float(c_mval)/float(c_im)
                            except: pass
                        comps.append({
                            'Account Number': c_acct,
                            'Address': c_addr,
                            'Zip Code': c_zip,
                            'Market Value': c_mval,
                            'Land Area': c_land,
                            'Building Area': c_im,
                            'Bedrooms': c_bed,
                            'Bathrooms': c_bath,
                            'Overall Rating': c_rating,
                            'Latitude': c_lat,
                            'Longitude': c_lon,
                            'Distance Miles': round(dist, 2),
                            'Price Per Sq Ft': round(ppsf, 2) if ppsf else None
                        })
                if comps:
                    break
        comps.sort(key=lambda r: (r['Distance Miles'], r['Price Per Sq Ft'] or 0))
        return comps[:limit]
    finally:
        cur.close(); conn.close()




def find_comparables_debug(acct: str, max_distance_miles: float = 5.0, size_tolerance: float = 0.2, land_tolerance: float = 0.2) -> Dict:
    """Return diagnostic info explaining why comparables may be missing.

    Keys:
      base_found: bool – subject property exists
      base_has_geo: bool – subject has latitude/longitude
      base_building_area: float|None
      base_land_area: float|None
      bbox_candidates: int – count of properties inside bounding box (before filters)
      filtered_size: int – remaining after size filter
      filtered_land: int – remaining after land area filter
      within_distance: int – remaining after distance haversine filter
      reason: str – concise explanation
    """
    info = {
        'base_found': False,
        'base_has_geo': False,
        'base_building_area': None,
        'base_land_area': None,
        'bbox_candidates': 0,
        'filtered_size': 0,
        'filtered_land': 0,
        'within_distance': 0,
        'reason': ''
    }
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        if not _table_exists(cur, 'property_geo'):
            info['reason'] = 'property_geo table missing (run import/geocode step).'
            return info
        cur.execute("""SELECT ra.acct, ra.land_ar, br.im_sq_ft, pg.latitude, pg.longitude
                      FROM real_acct ra
                      LEFT JOIN building_res br ON ra.acct = br.acct
                      LEFT JOIN property_geo pg ON ra.acct = pg.acct
                      WHERE ra.acct = ?""", (acct,))
        row = cur.fetchone()
        if not row:
            info['reason'] = 'Subject property not found.'; return info
        info['base_found'] = True
        _, land_ar, im_sq_ft, blat, blon = row
        if im_sq_ft and str(im_sq_ft).isdigit():
            try: info['base_building_area'] = float(im_sq_ft)
            except: pass
        if land_ar:
            try: info['base_land_area'] = float(land_ar)
            except: pass
        if blat is None or blon is None:
            info['reason'] = 'Subject missing geo coordinates (property_geo).' ; return info
        info['base_has_geo'] = True
        deg_buffer = max_distance_miles / 69.0
        cur.execute("""SELECT ra.acct, ra.land_ar, br.im_sq_ft, pg.latitude, pg.longitude
                      FROM real_acct ra
                      LEFT JOIN building_res br ON ra.acct = br.acct
                      JOIN property_geo pg ON ra.acct = pg.acct
                      WHERE pg.latitude BETWEEN ? AND ? AND pg.longitude BETWEEN ? AND ? AND ra.acct <> ?""",
                    (blat - deg_buffer, blat + deg_buffer, blon - deg_buffer, blon + deg_buffer, acct))
        candidates = cur.fetchall()
        info['bbox_candidates'] = len(candidates)
        im_min = (info['base_building_area'] * (1 - size_tolerance)) if info['base_building_area'] else None
        im_max = (info['base_building_area'] * (1 + size_tolerance)) if info['base_building_area'] else None
        land_min = (info['base_land_area'] * (1 - land_tolerance)) if info['base_land_area'] else None
        land_max = (info['base_land_area'] * (1 + land_tolerance)) if info['base_land_area'] else None
        after_size = []
        for c_acct, c_land, c_im, c_lat, c_lon in candidates:
            # size filter
            if im_min is not None and im_max is not None and c_im and c_im not in ('', '0'):
                try:
                    cimf = float(c_im)
                    if cimf < im_min or cimf > im_max:
                        continue
                except:
                    pass
            after_size.append((c_acct, c_land, c_im, c_lat, c_lon))
        info['filtered_size'] = len(after_size)
        after_land = []
        for c_acct, c_land, c_im, c_lat, c_lon in after_size:
            if land_min is not None and land_max is not None and c_land and c_land not in ('', '0'):
                try:
                    clandf = float(c_land)
                    if clandf < land_min or clandf > land_max:
                        continue
                except:
                    pass
            after_land.append((c_acct, c_land, c_im, c_lat, c_lon))
        info['filtered_land'] = len(after_land)
        within_dist = 0
        for c_acct, c_land, c_im, c_lat, c_lon in after_land:
            if c_lat is None or c_lon is None: continue
            try:
                d = haversine(float(blat), float(blon), float(c_lat), float(c_lon))
                if d <= max_distance_miles:
                    within_dist += 1
            except: pass
        info['within_distance'] = within_dist
        if not info['base_has_geo']:
            info['reason'] = 'Subject missing geo coordinates.'
        elif info['bbox_candidates'] == 0:
            info['reason'] = 'No candidates in geographic bounding box (likely sparse geo coverage).'
        elif info['within_distance'] == 0:
            info['reason'] = 'All candidates filtered out by size/land/distance constraints.'
        else:
            info['reason'] = 'Comparables available.'
        return info
    finally:
        cur.close(); conn.close()


def extract_excel_file(account: str = "", street: str = "", zip_code: str = "", exact_match: bool = False, owner: str = "") -> str:
    """Export search results to Excel if pandas available, else CSV.

    Mirrors search_properties column fallback: bedroom/bath/rating fields absent
    in current dataset so we export NULL placeholders for schema stability.
    """
    where_clauses = []
    file_name_parts = []
    params = []

    if account:
        where_clauses.append("CAST(ra.acct AS TEXT) LIKE ?")
        file_name_parts.append(account)
        params.append(f"%{account}%")
    if street:
        street_clean = street.strip().upper()
        if exact_match:
            where_clauses.append("UPPER(ra.site_addr_1) = ?")
            file_name_parts.append(f"{street} (exact)")
            params.append(street_clean)
        else:
            where_clauses.append("UPPER(ra.site_addr_1) LIKE ?")
            file_name_parts.append(street)
            params.append(f"%{street_clean}%")
    if zip_code:
        where_clauses.append("ra.site_addr_3 LIKE ?")
        file_name_parts.append(zip_code)
        params.append(f"%{zip_code}%")
    if owner:
        owner_clean = owner.strip().upper()
        where_clauses.append("( (ow.name IS NOT NULL AND UPPER(ow.name) LIKE ?) OR (ow.name IS NULL AND UPPER(ra.mailto) LIKE ?) )")
        params.extend([f"%{owner_clean}%", f"%{owner_clean}%"])
        # Keep filename concise: first word or truncated owner fragment
        short_owner = owner_clean.split()[0][:20]
        file_name_parts.append(short_owner)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Determine if property_geo table exists for export
    conn = get_connection(str(DB_PATH))
    cursor = wrap_cursor(conn)
    try:
        has_geo = _table_exists(cursor, 'property_geo')
    finally:
        cursor.close(); conn.close()
    geo_select = 'pg.latitude AS "Latitude", pg.longitude AS "Longitude"' if has_geo else 'NULL AS "Latitude", NULL AS "Longitude"'
    geo_join = "LEFT JOIN property_geo pg ON ra.acct = pg.acct" if has_geo else ""

    sql = f"""
    SELECT ra.site_addr_1 AS "Address",
         ra.site_addr_3 AS "Zip Code",
         br.eff AS "Build Year",
         pd.bedrooms AS "Bedrooms",
         pd.bathrooms AS "Bathrooms",
         br.im_sq_ft AS "Building Area",
         ra.land_val AS "Land Value",
         ra.bld_val AS "Building Value",
         CAST(ra.acct AS TEXT) AS "Account Number",
         ra.tot_mkt_val AS "Market Value",
         CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
             ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS "Price Per Sq Ft",
         ra.land_ar AS "Land Area",
         pd.property_type AS "Property Type",
         pd.amenities AS "Estimated Amenities",
         pd.overall_rating AS "Overall Rating",
         pd.quality_rating AS "Quality Rating",
         NULL AS "Value Rating",
        pd.rating_explanation AS "Rating Explanation",
        COALESCE(ow.name, ra.mailto) AS "Owner Name"
    FROM real_acct AS ra
    LEFT JOIN building_res AS br ON ra.acct = br.acct
    LEFT JOIN owners ow ON ra.acct = ow.acct
    LEFT JOIN property_derived pd ON ra.acct = pd.acct
    {geo_join}
    {where_sql}
    ORDER BY ra.tot_mkt_val DESC
    LIMIT 5000;
    """

    file_name = (" ".join(file_name_parts) + " ").strip() + " Home Info.xlsx"
    out_path = EXPORTS_DIR / file_name

    conn = get_connection(str(DB_PATH))
    cursor = wrap_cursor(conn)
    
    try:
        # Execute query with parameters
        try:
            cursor.execute(sql, params)
        except sqlite3.OperationalError as e:
            if 'no such table: owners' in str(e):
                cursor.execute("CREATE TABLE IF NOT EXISTS owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
                cursor.execute(sql, params)
            else:
                raise
        
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        try:
            import pandas as pd  # type: ignore
            df = pd.DataFrame(rows, columns=columns)
            if 'Price Per Sq Ft' in df.columns:
                df['Price Per Sq Ft'] = pd.to_numeric(df['Price Per Sq Ft'], errors='coerce')
                df['Price Per Sq Ft'] = df['Price Per Sq Ft'].map(lambda v: round(v,2) if v==v else v)
            df.to_excel(out_path, index=False)
        except Exception:
            csv_fallback = out_path.with_suffix('.csv')
            with open(csv_fallback, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(columns); writer.writerows(rows)
            return str(csv_fallback)
            
    finally:
        conn.close()
        
    return str(out_path)




if __name__ == "__main__":
    # Optional sampling for quicker test runs: set env FAST_LOAD_ROWS to an int
    fast_rows = os.getenv("FAST_LOAD_ROWS")
    if fast_rows and fast_rows.isdigit():
        rows = int(fast_rows)
        print(f"FAST LOAD enabled: limiting first {rows} rows per table.")
        files = {
            "building_res": TEXT_DIR / "building_res.txt",
            "land": TEXT_DIR / "land.txt",
            "real_acct": TEXT_DIR / "real_acct.txt",
        }
        conn = get_connection(str(DB_PATH))
        cursor = wrap_cursor(conn)
        try:
            for table, path in files.items():
                if not path.exists():
                    print(f"Skip {table}: file not found at {path}")
                    continue
                print(f"Loading sample of {table} from {path} ...")
                headers = create_table_from_csv(cursor, table, path)
                try:
                    with open(path, 'r', encoding=DEFAULT_ENCODING, newline='') as f:
                        reader = csv.reader(f, delimiter='\t')
                        next(reader)
                        batch = []
                        for i, row in enumerate(reader):
                            if i >= rows:
                                break
                            normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                            batch.append(normalized_row)
                        placeholders = ', '.join(['?' for _ in headers])
                        cursor.executemany(f'INSERT INTO {table} VALUES ({placeholders})', batch)
                except (UnicodeDecodeError, LookupError):
                    with open(path, 'r', encoding='utf-8', newline='') as f:
                        reader = csv.reader(f, delimiter='\t')
                        next(reader)
                        batch = []
                        for i, row in enumerate(reader):
                            if i >= rows:
                                break
                            normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                            batch.append(normalized_row)
                        placeholders = ', '.join(['?' for _ in headers])
                        cursor.executemany(f'INSERT INTO {table} VALUES ({placeholders})', batch)
            conn.commit(); print("Sample load complete.")
        finally:
            conn.close()
    else:
        load_data_to_sqlite()
