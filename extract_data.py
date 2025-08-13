import os
import csv
import sqlite3
from pathlib import Path

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


def search_properties(account: str = "", street: str = "", zip_code: str = "", exact_match: bool = False) -> list:
    """Search for properties and return results as list of dictionaries"""
    where_clauses = []
    params = []

    if account:
        where_clauses.append("CAST(ra.acct AS TEXT) LIKE ?")
        params.append(f"%{account.strip()}%")
    if street:
        # Clean and improve street search
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
    LIMIT 100;
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        # Convert to list of dictionaries
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
        
        return results
        
    finally:
        conn.close()


def extract_excel_file(account: str = "", street: str = "", zip_code: str = "", exact_match: bool = False) -> str:
    """Export search results to CSV using built-in CSV writer"""
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

    file_name = (" ".join(file_name_parts) + " ").strip() + " Home Info.csv"
    out_path = EXPORTS_DIR / file_name

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Execute query with parameters
        cursor.execute(sql, params)
        
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        # Format the data for CSV export
        formatted_rows = []
        price_per_sqft_index = None
        
        # Find the index of 'Price Per Sq Ft' column
        for i, col in enumerate(columns):
            if col == 'Price Per Sq Ft':
                price_per_sqft_index = i
                break
        
        # Format each row
        for row in rows:
            formatted_row = list(row)
            # Format price per sq ft to 2 decimal places
            if price_per_sqft_index is not None and formatted_row[price_per_sqft_index] is not None:
                try:
                    formatted_row[price_per_sqft_index] = f"{float(formatted_row[price_per_sqft_index]):.2f}"
                except (ValueError, TypeError):
                    # Keep original value if formatting fails
                    pass
            formatted_rows.append(formatted_row)
        
        # Write to CSV 
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(formatted_rows)
            
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
