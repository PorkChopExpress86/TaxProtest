import os
import csv
import math
import sqlite3
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEXT_DIR = BASE_DIR / "text_files"
EXPORTS_DIR = BASE_DIR / "Exports"
EXPORTS_DIR.mkdir(exist_ok=True)

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
        
    finally:
        conn.close()


def search_properties(account: str = "", street: str = "", zip_code: str = "", owner: str = "", exact_match: bool = False) -> List[Dict]:
    """Search for properties (adds owner filtering)."""
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
        where_clauses.append("(UPPER(ra.own_name_1) LIKE ? OR UPPER(ra.own_name_2) LIKE ?)")
        o = owner.strip().upper()
        params.extend([f"%{o}%", f"%{o}%"])
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"""
    SELECT ra.site_addr_1 AS 'Address', ra.site_addr_3 AS 'Zip Code', br.eff AS 'Build Year',
           br.est_bedrooms AS 'Bedrooms', br.est_bathrooms AS 'Bathrooms', br.im_sq_ft AS 'Building Area',
           ra.land_val AS 'Land Value', ra.bld_val AS 'Building Value', CAST(ra.acct AS TEXT) AS 'Account Number',
           ra.tot_mkt_val AS 'Market Value',
           CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
                ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS 'Price Per Sq Ft',
           ra.land_ar AS 'Land Area', br.property_features AS 'Property Type', br.est_amenities AS 'Estimated Amenities',
           br.overall_rating AS 'Overall Rating', br.quality_rating AS 'Quality Rating', br.value_rating AS 'Value Rating',
           br.rating_explanation AS 'Rating Explanation', pg.latitude AS 'Latitude', pg.longitude AS 'Longitude'
    FROM real_acct ra
    LEFT JOIN building_res br ON ra.acct = br.acct
    LEFT JOIN property_geo pg ON ra.acct = pg.acct
    {where_sql}
    ORDER BY br.overall_rating DESC, ra.tot_mkt_val DESC
    LIMIT 100;"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
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
        cur.execute("""SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                              br.est_bedrooms, br.est_bathrooms, pg.latitude, pg.longitude
                       FROM real_acct ra
                       LEFT JOIN building_res br ON ra.acct = br.acct
                       LEFT JOIN property_geo pg ON ra.acct = pg.acct
                       WHERE ra.acct = ?""", (acct,))
        base = cur.fetchone()
        if not base:
            return []
        (acct, addr, zipc, mval, land_ar, im_sq_ft, bedrooms, bathrooms, blat, blon) = base
        if blat is None or blon is None:
            return []
        im_min = (float(im_sq_ft) * (1 - size_tolerance)) if im_sq_ft else None
        im_max = (float(im_sq_ft) * (1 + size_tolerance)) if im_sq_ft else None
        land_min = (float(land_ar) * (1 - land_tolerance)) if land_ar else None
        land_max = (float(land_ar) * (1 + land_tolerance)) if land_ar else None
        deg_buffer = max_distance_miles / 69.0
        cur.execute("""SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft,
                             br.est_bedrooms, br.est_bathrooms, pg.latitude, pg.longitude
                      FROM real_acct ra
                      LEFT JOIN building_res br ON ra.acct = br.acct
                      JOIN property_geo pg ON ra.acct = pg.acct
                      WHERE pg.latitude BETWEEN ? AND ? AND pg.longitude BETWEEN ? AND ? AND ra.acct <> ?""",
                    (blat - deg_buffer, blat + deg_buffer, blon - deg_buffer, blon + deg_buffer, acct))
        comps = []
        for row in cur.fetchall():
            (c_acct, c_addr, c_zip, c_mval, c_land, c_im, c_bed, c_bath, c_lat, c_lon) = row
            if c_lat is None or c_lon is None:
                continue
            if im_sq_ft and c_im and im_min is not None and im_max is not None:
                if not (im_min <= float(c_im) <= im_max):
                    continue
            if land_ar and c_land and land_min is not None and land_max is not None:
                if not (land_min <= float(c_land) <= land_max):
                    continue
            if bedrooms and c_bed and abs(float(c_bed) - float(bedrooms)) > 1:
                continue
            if bathrooms and c_bath and abs(float(c_bath) - float(bathrooms)) > 1:
                continue
            dist = haversine(float(blat), float(blon), float(c_lat), float(c_lon))
            if dist <= max_distance_miles:
                ppsf = None
                if c_im and c_mval and str(c_im) not in ('0',''):
                    try: ppsf = float(c_mval)/float(c_im)
                    except Exception: pass
                comps.append({'Account': c_acct, 'Address': c_addr, 'Zip': c_zip, 'Market Value': c_mval,
                              'Land Area': c_land, 'Building Area': c_im, 'Bedrooms': c_bed, 'Bathrooms': c_bath,
                              'Latitude': c_lat, 'Longitude': c_lon, 'Distance (miles)': round(dist,2),
                              'Price Per Sq Ft': round(ppsf,2) if ppsf else None})
        comps.sort(key=lambda r: (r['Distance (miles)'], r['Price Per Sq Ft'] or 0))
        return comps[:limit]
    finally:
        cur.close(); conn.close()


def extract_excel_file(account: str = "", street: str = "", zip_code: str = "", exact_match: bool = False, owner: str = "") -> str:
    """Export search results to Excel if pandas available, else CSV."""
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
        # Owner name filter (case-insensitive, matches either owner name field)
        owner_clean = owner.strip().upper()
        where_clauses.append("(UPPER(ra.own_name_1) LIKE ? OR UPPER(ra.own_name_2) LIKE ?)")
        params.extend([f"%{owner_clean}%", f"%{owner_clean}%"])
        # Keep filename concise: first word or truncated owner fragment
        short_owner = owner_clean.split()[0][:20]
        file_name_parts.append(short_owner)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
    SELECT ra.site_addr_1 AS 'Address',
           ra.site_addr_3 AS 'Zip Code',
           br.eff AS 'Build Year',
           br.est_bedrooms AS 'Bedrooms',
           br.est_bathrooms AS 'Bathrooms',
           br.im_sq_ft AS 'Building Area',
           ra.land_val AS 'Land Value',
           ra.bld_val AS 'Building Value',
           CAST(ra.acct AS TEXT) AS 'Account Number',
           ra.tot_mkt_val AS 'Market Value',
           CASE WHEN br.im_sq_ft IS NULL OR br.im_sq_ft = '' OR br.im_sq_ft = '0' THEN NULL
                ELSE (CAST(ra.tot_mkt_val AS FLOAT) / CAST(br.im_sq_ft AS FLOAT)) END AS 'Price Per Sq Ft',
           ra.land_ar AS 'Land Area',
           br.property_features AS 'Property Type',
           br.est_amenities AS 'Estimated Amenities',
           br.overall_rating AS 'Overall Rating',
           br.quality_rating AS 'Quality Rating',
           br.value_rating AS 'Value Rating',
           br.rating_explanation AS 'Rating Explanation'
    FROM real_acct AS ra
    LEFT JOIN building_res AS br ON ra.acct = br.acct
    {where_sql}
    ORDER BY br.overall_rating DESC, ra.tot_mkt_val DESC
    LIMIT 5000;
    """

    file_name = (" ".join(file_name_parts) + " ").strip() + " Home Info.xlsx"
    out_path = EXPORTS_DIR / file_name

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Execute query with parameters
        cursor.execute(sql, params)
        
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
