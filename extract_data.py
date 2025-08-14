import os
import csv
import math
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEXT_DIR = BASE_DIR / "text_files"
EXPORTS_DIR = BASE_DIR / "Exports"
EXPORTS_DIR.mkdir(exist_ok=True)
EXTRACTED_DIR = BASE_DIR / "extracted"

DB_PATH = BASE_DIR / 'data' / 'database.sqlite'


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
    # Increase CSV field size limit
    csv.field_size_limit(1000000)
    
    try:
        with open(csv_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)  # Skip header row
            
            batch = []
            for row_num, row in enumerate(reader, 1):
                # Pad or truncate row to match headers
                normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                batch.append(normalized_row)
                
                if len(batch) >= batch_size:
                    placeholders = ', '.join(['?' for _ in headers])
                    cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                    print(f"  inserted batch ending at row {row_num}")
                    batch = []
            
            # Insert remaining rows
            if batch:
                placeholders = ', '.join(['?' for _ in headers])
                cursor.executemany(f'INSERT INTO {table_name} VALUES ({placeholders})', batch)
                print(f"  inserted final batch of {len(batch)} rows")
                
    except UnicodeDecodeError:
        if encoding != 'utf-8':
            load_csv_to_table(cursor, table_name, csv_path, headers, encoding='utf-8', batch_size=batch_size)
        else:
            raise


def load_data_to_sqlite():
    files = {
        "building_res": TEXT_DIR / "building_res.txt",
        "real_acct": TEXT_DIR / "real_acct.txt",
        # Note: land.txt doesn't seem to be extracted, so we'll skip it for now
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        for table, path in files.items():
            if not path.exists():
                print(f"Skip {table}: file not found at {path}")
                continue
            print(f"Loading {table} from {path} ...")
            
            headers = create_table_from_csv(cursor, table, path)
            load_csv_to_table(cursor, table, path, headers)
            
        conn.commit()
        print("All available files loaded into SQLite.")

        # Load owners.txt if present
        owners_path = TEXT_DIR / "owners.txt"
        if owners_path.exists():
            print(f"Loading owners from {owners_path} ...")
            cursor.execute("DROP TABLE IF EXISTS owners")
            cursor.execute("CREATE TABLE owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
            with open(owners_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline()  # skip header
                batch = []
                for i, line in enumerate(f, 1):
                    parts = line.rstrip('\n').split('\t')
                    if len(parts) < 5:
                        parts.extend([''] * (5 - len(parts)))
                    acct, ln_num, name, aka, pct_own = [p.strip() for p in parts[:5]]
                    batch.append((acct, ln_num, name, aka, pct_own))
                    if len(batch) >= 10000:
                        cursor.executemany('INSERT INTO owners VALUES (?,?,?,?,?)', batch)
                        batch.clear()
                if batch:
                    cursor.executemany('INSERT INTO owners VALUES (?,?,?,?,?)', batch)
            conn.commit()
            cursor.execute('SELECT COUNT(1) FROM owners')
            print(f"Loaded {cursor.fetchone()[0]} owner rows.")
        else:
            # Ensure empty owners table exists so LEFT JOIN does not fail
            cursor.execute("CREATE TABLE IF NOT EXISTS owners (acct TEXT, ln_num TEXT, name TEXT, aka TEXT, pct_own TEXT)")
            conn.commit()
            print("owners.txt not found; created empty owners table.")

        # Load descriptor files for quality code and land use (if present)
        def load_descriptor(filename: str, table: str, expected_cols: int = 2):
            for base in (TEXT_DIR, EXTRACTED_DIR):
                p = base / filename
                if p.exists():
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        cursor.execute(f"CREATE TABLE {table} (col1 TEXT, col2 TEXT, col3 TEXT, col4 TEXT, col5 TEXT)")
                        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                            header = f.readline()
                            batch = []
                            for line in f:
                                parts = line.rstrip('\n').split('\t')
                                parts.extend([''] * (5 - len(parts)))
                                batch.append(tuple(parts[:5]))
                                if len(batch) >= 5000:
                                    cursor.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?)", batch)
                                    batch.clear()
                            if batch:
                                cursor.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?)", batch)
                        conn.commit()
                        print(f"Loaded descriptor {filename} into {table}")
                    except Exception as e:
                        print(f"Failed loading descriptor {filename}: {e}")
                    break
        load_descriptor('desc_r_07_quality_code.txt', 'quality_code_desc')
        load_descriptor('desc_r_15_land_usecode.txt', 'land_use_code_desc')

        # Load additional tables for deeper bed/bath parsing
        additional_files = {}
        for fname in ['fixtures.txt', 'building_other.txt', 'structural_elem1.txt', 'structural_elem2.txt', 'extra_features.txt']:
            for base_dir in [TEXT_DIR, EXTRACTED_DIR]:
                fpath = base_dir / fname
                if fpath.exists():
                    additional_files[fname] = fpath
                    break

        # Load structural and feature data for room counting
        for fname, fpath in additional_files.items():
            table_name = fname.replace('.txt', '').replace('-', '_')
            try:
                headers = create_table_from_csv(cursor, table_name, fpath)
                load_csv_to_table(cursor, table_name, fpath, headers, batch_size=5000)
                print(f"Loaded {fname} for room analysis")
            except Exception as e:
                print(f"Failed to load {fname}: {e}")

        # Create derived property metrics (bedrooms, bathrooms, property type, quality rating)
        cursor.execute("DROP TABLE IF EXISTS property_derived")
        cursor.execute("""
            CREATE TABLE property_derived (
                acct TEXT PRIMARY KEY,
                bedrooms INTEGER,
                bathrooms REAL,
                property_type TEXT,
                quality_code TEXT,
                quality_rating REAL,
                overall_rating REAL,
                rating_explanation TEXT,
                amenities TEXT
            )
        """)

        # Build quality code mapping based on actual data from quality_code_desc table
        quality_rank = {}
        current_year = datetime.now().year

        # Get quality codes from quality_code_desc table and building_res data
        try:
            cursor.execute("SELECT col1, col2 FROM quality_code_desc WHERE col1<>'' AND col2<>''")
            quality_desc_data = cursor.fetchall()
            print(f"Quality descriptions found: {quality_desc_data}")
            
            # Map quality codes to numeric scores based on description
            quality_mapping = {
                'X ': 10.0,  # Superior
                'A ': 9.0,   # Excellent  
                'B ': 7.0,   # Good
                'C ': 5.0,   # Average
                'D ': 3.0,   # Low
                'E ': 1.5,   # Very Low
                'F ': 1.0    # Poor
            }
            
            # Also check for variations without space
            for code in ['X', 'A', 'B', 'C', 'D', 'E', 'F']:
                if code not in quality_mapping:
                    quality_mapping[code] = quality_mapping.get(code + ' ', 5.0)
            
            quality_rank = quality_mapping
            print(f"Quality ranking system: {quality_rank}")
            
        except Exception as e:
            print(f"Error setting up quality ranking: {e}")
            # Fallback quality ranking
            quality_rank = {
                'X ': 10.0, 'X': 10.0,  # Superior
                'A ': 9.0, 'A': 9.0,    # Excellent  
                'B ': 7.0, 'B': 7.0,    # Good
                'C ': 5.0, 'C': 5.0,    # Average
                'D ': 3.0, 'D': 3.0,    # Low
                'E ': 1.5, 'E': 1.5,    # Very Low
                'F ': 1.0, 'F': 1.0     # Poor
            }

        # Land use / property type mapping from descriptor if possible (assume code in col1, desc in col2)
        land_use_map = {}
        try:
            cursor.execute("SELECT col1, col2 FROM land_use_code_desc WHERE col1<>''")
            land_use_map = {r[0]: r[1] for r in cursor.fetchall() if r[0]}
        except Exception:
            pass

        # Enhanced regex patterns for bed/bath extraction from descriptions
        bed_patterns = [
            re.compile(r'\b(\d{1,2})\s*(?:BR|BED|BEDROOM)S?\b', re.IGNORECASE),
            re.compile(r'(\d{1,2})\s*[/\-]\s*(\d{1,2})(?:\s*[/\-]\s*\d{1,2})?\b'),  # 3/2 format
            re.compile(r'\b(\d{1,2})\s*BED\b', re.IGNORECASE)
        ]
        bath_patterns = [
            re.compile(r'\b(\d{1,2}(?:\.\d)?)\s*(?:BA|BATH|BATHROOM)S?\b', re.IGNORECASE),
            re.compile(r'\b(\d{1,2})\s*[/\-]\s*(\d{1,2}(?:\.\d)?)\b'),  # 3/2.5 format  
            re.compile(r'(\d{1,2}(?:\.\d)?)\s*BATH\b', re.IGNORECASE)
        ]

        # Collect all property data for comprehensive parsing
        cursor.execute("SELECT acct, dscr, structure_dscr, eff, qa_cd, property_use_cd FROM building_res")
        building_data = {row[0]: row[1:] for row in cursor.fetchall()}

        # Get explicit bedroom/bathroom counts from fixtures.txt
        fixture_counts = {}
        try:
            cursor.execute("SELECT acct, type, type_dscr, units FROM fixtures WHERE type IS NOT NULL AND units IS NOT NULL")
            for acct, ftype, type_desc, units in cursor.fetchall():
                # Use trimmed account to match building_res padded accounts
                acct_trimmed = acct.strip()
                if acct_trimmed not in fixture_counts:
                    fixture_counts[acct_trimmed] = {'bedrooms': 0, 'bathrooms': 0.0}
                
                try:
                    unit_count = float(units) if units else 0
                except:
                    unit_count = 0
                
                # Map fixture types to bedroom/bathroom counts
                ftype = ftype.strip().upper() if ftype else ''
                desc = (type_desc or '').upper()
                
                # Bedroom fixtures
                if ftype == 'RMB' or 'BEDROOM' in desc:
                    fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count)
                elif ftype.startswith('AP') and 'BEDROOM' in desc:
                    # Apartment units: AP1=1-bed, AP2=2-bed, AP3=3-bed
                    if ftype == 'AP1':
                        fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count) * 1
                    elif ftype == 'AP2':
                        fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count) * 2
                    elif ftype == 'AP3':
                        fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count) * 3
                    elif ftype == 'AP4':
                        fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count) * 4
                
                # Bathroom fixtures
                if ftype == 'RMF' or 'FULL BATH' in desc:
                    fixture_counts[acct_trimmed]['bathrooms'] += unit_count
                elif ftype == 'RMH' or 'HALF BATH' in desc:
                    fixture_counts[acct_trimmed]['bathrooms'] += unit_count * 0.5
                elif 'BATH' in desc and ftype.startswith('RM'):
                    fixture_counts[acct_trimmed]['bathrooms'] += unit_count
                
        except sqlite3.OperationalError:
            print("fixtures table not available")

        # Pre-load amenities data for all properties
        amenities_data = {}
        try:
            cursor.execute("SELECT acct, l_dscr FROM extra_features WHERE l_dscr IS NOT NULL")
            print("Loading amenities data...")
            for acct, desc in cursor.fetchall():
                desc = desc.strip() if desc else ""
                if desc and any(keyword in desc.upper() for keyword in ['POOL', 'GARAGE', 'DECK', 'PATIO', 'FIRE', 'SPA']):
                    # Use trimmed account to match fixtures table format
                    acct_trimmed = acct.strip()
                    if acct_trimmed not in amenities_data:
                        amenities_data[acct_trimmed] = []
                    amenities_data[acct_trimmed].append(desc)
            print(f"Loaded amenities for {len(amenities_data)} properties")
        except sqlite3.OperationalError:
            print("extra_features table not available")

        # Get room counts from structural elements and features for fallback
        room_counts = {}
        
        # Parse structural elements for room indicators
        for table in ['structural_elem1', 'structural_elem2']:
            try:
                cursor.execute(f"SELECT acct, type_dscr FROM {table} WHERE type_dscr IS NOT NULL")
                for acct, desc in cursor.fetchall():
                    if acct not in room_counts:
                        room_counts[acct] = {'bed_hints': [], 'bath_hints': []}
                    desc_upper = desc.upper()
                    if any(word in desc_upper for word in ['BEDROOM', 'BED']):
                        room_counts[acct]['bed_hints'].append(desc)
                    if any(word in desc_upper for word in ['BATHROOM', 'BATH', 'TOILET']):
                        room_counts[acct]['bath_hints'].append(desc)
            except sqlite3.OperationalError:
                pass  # Table doesn't exist

        # Parse extra features for room counts
        try:
            cursor.execute("SELECT acct, count, s_dscr, l_dscr FROM extra_features WHERE s_dscr IS NOT NULL OR l_dscr IS NOT NULL")
            for acct, count, s_desc, l_desc in cursor.fetchall():
                if acct not in room_counts:
                    room_counts[acct] = {'bed_hints': [], 'bath_hints': []}
                desc = f"{s_desc or ''} {l_desc or ''}".upper()
                try:
                    count_val = int(count) if count and count.isdigit() else 0
                except:
                    count_val = 0
                
                if any(word in desc for word in ['BEDROOM', 'BED']) and count_val > 0:
                    room_counts[acct]['bed_hints'].append(f"COUNT:{count_val}")
                if any(word in desc for word in ['BATHROOM', 'BATH', 'TOILET', 'RESTROOM']) and count_val > 0:
                    room_counts[acct]['bath_hints'].append(f"COUNT:{count_val}")
        except sqlite3.OperationalError:
            pass

        # Parse building_other for additional room data
        try:
            cursor.execute("SELECT acct, structure_dscr, dscr, notes FROM building_other WHERE structure_dscr IS NOT NULL OR dscr IS NOT NULL OR notes IS NOT NULL")
            for acct, struct_desc, desc, notes in cursor.fetchall():
                if acct not in room_counts:
                    room_counts[acct] = {'bed_hints': [], 'bath_hints': []}
                text = f"{struct_desc or ''} {desc or ''} {notes or ''}"
                if text.strip():
                    room_counts[acct]['bed_hints'].append(text)
                    room_counts[acct]['bath_hints'].append(text)
        except sqlite3.OperationalError:
            pass

        # Derive bedroom/bathroom counts (prioritize fixtures.txt data)
        derived = {}
        for acct, (dscr, structure_dscr, eff, qa_cd, property_use_cd) in building_data.items():
            # Start with explicit fixture counts if available (account format fix)
            acct_trimmed = acct.strip()
            beds = fixture_counts.get(acct_trimmed, {}).get('bedrooms', None)
            baths = fixture_counts.get(acct_trimmed, {}).get('bathrooms', None)
            
            # If no fixture data, try text parsing as fallback
            if beds is None or baths is None:
                # Combine all text sources
                all_text = []
                if dscr: all_text.append(dscr)
                if structure_dscr: all_text.append(structure_dscr)
                
                # Add room hints from other tables
                if acct in room_counts:
                    all_text.extend(room_counts[acct]['bed_hints'])
                    all_text.extend(room_counts[acct]['bath_hints'])
                
                combined_text = ' '.join(all_text)
                
                # Extract bedrooms if not from fixtures
                if beds is None:
                    for pattern in bed_patterns:
                        matches = pattern.findall(combined_text)
                        if matches:
                            if isinstance(matches[0], tuple):
                                # Handle 3/2 format - first number is bedrooms
                                try: beds = max(beds or 0, int(matches[0][0]))
                                except: pass
                            else:
                                try: beds = max(beds or 0, int(matches[0]))
                                except: pass
                
                # Look for explicit count hints for bedrooms
                if beds is None:
                    for hint in room_counts.get(acct, {}).get('bed_hints', []):
                        if 'COUNT:' in hint:
                            try:
                                count_val = int(hint.split('COUNT:')[1])
                                beds = max(beds or 0, count_val)
                            except:
                                pass
                
                # Extract bathrooms if not from fixtures
                if baths is None:
                    for pattern in bath_patterns:
                        matches = pattern.findall(combined_text)
                        if matches:
                            if isinstance(matches[0], tuple) and len(matches[0]) > 0:
                                # Handle 3/2.5 format - second number is bathrooms
                                try: 
                                    if len(matches[0]) > 1:
                                        bath_val = float(matches[0][1])
                                    else:
                                        bath_val = float(matches[0][0])
                                    baths = max(baths or 0, bath_val)
                                except: pass
                            elif matches[0]:  # Single string match
                                try: baths = max(baths or 0, float(str(matches[0])))
                                except: pass
                
                # Look for explicit bathroom count hints
                if baths is None:
                    for hint in room_counts.get(acct, {}).get('bath_hints', []):
                        if 'COUNT:' in hint:
                            try:
                                count_val = float(hint.split('COUNT:')[1])
                                baths = max(baths or 0, count_val)
                            except:
                                pass

            derived[acct] = {'bedrooms': beds, 'bathrooms': baths, 'eff': eff, 'qa_cd': qa_cd, 'use': property_use_cd}

        rows = []
        for acct, data in derived.items():
            qa_cd = (data['qa_cd'] or '').strip() if data['qa_cd'] else ''
            quality_rating = quality_rank.get(qa_cd, None)
            
            # Age score (newer is higher, scaled 1-10)
            age_score = None
            if data['eff'] and str(data['eff']).isdigit():
                build_year = int(data['eff'])
                age = max(0, current_year - build_year)
                # More generous age scoring: properties lose 0.05 points per year
                age_score = max(1.0, min(10.0, 10 - (age * 0.05)))
            
            overall_rating = None
            if quality_rating is not None:
                if age_score is not None:
                    # Combine quality (70%) and age (30%)
                    overall_rating = round((quality_rating * 0.7 + age_score * 0.3), 1)
                else:
                    # Use quality rating alone if no age data
                    overall_rating = quality_rating
            elif age_score is not None:
                # Use age score alone if no quality data
                overall_rating = age_score
            
            prop_type = None
            if data['use'] and data['use'] in land_use_map:
                prop_type = land_use_map[data['use']]
            
            rating_expl = None
            if overall_rating is not None:
                components = []
                if quality_rating is not None:
                    components.append(f"quality {qa_cd or 'N/A'} ({quality_rating}/10)")
                if age_score is not None and data['eff']:
                    components.append(f"age ({data['eff']}, {age_score:.1f}/10)")
                rating_expl = f"Score: {', '.join(components)}"[:180]
            
            # Extract amenities from pre-loaded data (account format fix)
            amenities = None
            acct_trimmed = acct.strip()
            if acct_trimmed in amenities_data:
                amenity_list = amenities_data[acct_trimmed][:5]  # Limit to first 5 amenities
                amenities = ', '.join(amenity_list) if amenity_list else None
            
            rows.append((acct, data['bedrooms'], data['bathrooms'], prop_type, qa_cd, quality_rating, overall_rating, rating_expl, amenities))

        if rows:
            cursor.executemany("INSERT INTO property_derived VALUES (?,?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            print(f"Inserted {len(rows)} derived property rows.")
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_geo'")
        has_geo = cursor.fetchone() is not None
    finally:
        cursor.close(); conn.close()

    geo_join = "LEFT JOIN property_geo pg ON ra.acct = pg.acct" if has_geo else ""
    geo_select = "pg.latitude AS 'Latitude', pg.longitude AS 'Longitude'" if has_geo else "NULL AS 'Latitude', NULL AS 'Longitude'"

    sql = f"""
    SELECT ra.site_addr_1 AS 'Address',
         ra.site_addr_3 AS 'Zip Code',
         br.eff AS 'Build Year',
         pd.bedrooms AS 'Bedrooms',
         pd.bathrooms AS 'Bathrooms',
         br.im_sq_ft AS 'Building Area',
         ra.land_val AS 'Land Value',
         ra.bld_val AS 'Building Value',
         CAST(ra.acct AS TEXT) AS 'Account Number',
         ra.tot_mkt_val AS 'Market Value',
         CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
             ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS 'Price Per Sq Ft',
         ra.land_ar AS 'Land Area',
         pd.property_type AS 'Property Type',
         pd.amenities AS 'Estimated Amenities',
        pd.overall_rating AS 'Overall Rating',
        pd.quality_rating AS 'Quality Rating',
        NULL AS 'Value Rating',
        pd.rating_explanation AS 'Rating Explanation',
        COALESCE(ow.name, ra.mailto) AS 'Owner Name',
           {geo_select}
    FROM real_acct ra
    LEFT JOIN building_res br ON ra.acct = br.acct
    LEFT JOIN owners ow ON ra.acct = ow.acct
    LEFT JOIN property_derived pd ON ra.acct = pd.acct
    {geo_join}
    {where_sql}
    ORDER BY ra.site_addr_1 ASC
    LIMIT 100;"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def find_comparables(acct: str, max_distance_miles: float = 5.0, size_tolerance: float = 0.2, land_tolerance: float = 0.2, limit: int = 50) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
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
        im_min = (float(im_sq_ft) * (1 - size_tolerance)) if im_sq_ft else None
        im_max = (float(im_sq_ft) * (1 + size_tolerance)) if im_sq_ft else None
        land_min = (float(land_ar) * (1 - land_tolerance)) if land_ar else None
        land_max = (float(land_ar) * (1 + land_tolerance)) if land_ar else None
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
        for row in cur.fetchall():
            (c_acct, c_addr, c_zip, c_mval, c_land, c_im, c_bed, c_bath, c_lat, c_lon, c_rating) = row
            if c_lat is None or c_lon is None:
                continue
            if im_sq_ft and c_im and im_min is not None and im_max is not None and not (im_min <= float(c_im) <= im_max):
                continue
            if land_ar and c_land and land_min is not None and land_max is not None and not (land_min <= float(c_land) <= land_max):
                continue
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
        comps.sort(key=lambda r: (r['Distance Miles'], r['Price Per Sq Ft'] or 0))
        return comps[:limit]
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_geo'")
        has_geo = cursor.fetchone() is not None
    finally:
        cursor.close(); conn.close()
    geo_select = "pg.latitude AS 'Latitude', pg.longitude AS 'Longitude'" if has_geo else "NULL AS 'Latitude', NULL AS 'Longitude'"
    geo_join = "LEFT JOIN property_geo pg ON ra.acct = pg.acct" if has_geo else ""

    sql = f"""
    SELECT ra.site_addr_1 AS 'Address',
         ra.site_addr_3 AS 'Zip Code',
         br.eff AS 'Build Year',
         pd.bedrooms AS 'Bedrooms',
         pd.bathrooms AS 'Bathrooms',
         br.im_sq_ft AS 'Building Area',
         ra.land_val AS 'Land Value',
         ra.bld_val AS 'Building Value',
         CAST(ra.acct AS TEXT) AS 'Account Number',
         ra.tot_mkt_val AS 'Market Value',
         CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
             ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS 'Price Per Sq Ft',
         ra.land_ar AS 'Land Area',
         pd.property_type AS 'Property Type',
         pd.amenities AS 'Estimated Amenities',
         pd.overall_rating AS 'Overall Rating',
         pd.quality_rating AS 'Quality Rating',
         NULL AS 'Value Rating',
        pd.rating_explanation AS 'Rating Explanation',
        COALESCE(ow.name, ra.mailto) AS 'Owner Name'
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
        # For fast mode, create a simple version that stops after N rows
        files = {
            "building_res": TEXT_DIR / "building_res.txt",
            "land": TEXT_DIR / "land.txt",
            "real_acct": TEXT_DIR / "real_acct.txt",
        }
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            for table, path in files.items():
                if not path.exists():
                    print(f"Skip {table}: file not found at {path}")
                    continue
                print(f"Loading sample of {table} from {path} ...")
                
                # Create table and load limited rows
                headers = create_table_from_csv(cursor, table, path)
                
                # Load only first N rows
                try:
                    with open(path, 'r', encoding='mbcs', newline='') as f:
                        reader = csv.reader(f, delimiter='\t')
                        next(reader)  # Skip header
                        
                        batch = []
                        for i, row in enumerate(reader):
                            if i >= rows:
                                break
                            normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                            batch.append(normalized_row)
                        
                        placeholders = ', '.join(['?' for _ in headers])
                        cursor.executemany(f'INSERT INTO {table} VALUES ({placeholders})', batch)
                        
                except UnicodeDecodeError:
                    # Try utf-8 encoding
                    with open(path, 'r', encoding='utf-8', newline='') as f:
                        reader = csv.reader(f, delimiter='\t')
                        next(reader)  # Skip header
                        
                        batch = []
                        for i, row in enumerate(reader):
                            if i >= rows:
                                break
                            normalized_row = row[:len(headers)] + [''] * (len(headers) - len(row))
                            batch.append(normalized_row)
                        
                        placeholders = ', '.join(['?' for _ in headers])
                        cursor.executemany(f'INSERT INTO {table} VALUES ({placeholders})', batch)
                        
            conn.commit()
            print("Sample load complete.")
        finally:
            conn.close()
    else:
        load_data_to_sqlite()
