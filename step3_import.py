"""
Step 3: Import Harris County Tax Data into SQLite
===============================================

This script imports extracted text files into SQLite database with amenities
processing and tracks import hashes to avoid unnecessary re-imports.
"""

import csv
import hashlib
import json
import os
import sqlite3
from pathlib import Path

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEXT_FILES_DIR = BASE_DIR / "text_files"
DB_PATH = BASE_DIR / 'data' / 'database.sqlite'
HASH_FILE = BASE_DIR / "data" / "import_hashes.json"

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
        
        rows.append((acct, bedrooms, bathrooms, prop_type, qa_cd, 
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
    # Define core files to import
    core_files = {
        "real_acct": TEXT_FILES_DIR / "real_acct.txt",
        "building_res": TEXT_FILES_DIR / "building_res.txt",
    }
    
    # Define optional files
    optional_files = {
        "fixtures": TEXT_FILES_DIR / "fixtures.txt",
        "extra_features": TEXT_FILES_DIR / "extra_features.txt", 
        "owners": TEXT_FILES_DIR / "owners.txt",
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Import core files (required)
        for table, path in core_files.items():
            if not path.exists():
                print(f"❌ CRITICAL: {table} file not found at {path}")
                print("   Cannot proceed without core files. Run step2_extract.py first.")
                return False
                
            print(f"📥 Loading {table} from {path.name}...")
            headers = create_table_from_csv(cursor, table, path)
            load_csv_to_table(cursor, table, path, headers)
        
        # Import optional files (for enhanced features)
        for table, path in optional_files.items():
            if path.exists():
                print(f"📥 Loading {table} from {path.name}...")
                headers = create_table_from_csv(cursor, table, path)
                load_csv_to_table(cursor, table, path, headers)
            else:
                print(f"⚠️  Optional file {path.name} not found, skipping {table}")
        
        # Create property_derived table with amenities
        print(f"🏗️  Building property_derived table with amenities...")
        populate_property_derived(cursor)
        
        # Create indexes for better performance
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
        
        conn.commit()
        print("✅ All data imported successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during import: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    print("🗃️  Harris County Tax Data SQLite Importer")
    print("=" * 50)
    
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
    existing_hashes = load_existing_hashes()
    
    # Check if import is needed
    should_import = True
    if "combined_hash" in existing_hashes and existing_hashes["combined_hash"] == current_combined_hash:
        if DB_PATH.exists():
            print("⏭️  Database up to date (file hashes match)")
            print(f"   Database: {DB_PATH}")
            
            # Show database stats
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
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
        else:
            print("🔄 Database file missing, will import...")
    else:
        print("🔄 Data files changed, importing...")
    
    if should_import:
        print(f"\n📁 Importing from files: {', '.join(existing_files)}")
        
        if import_data_to_sqlite():
            # Save new hash
            new_hashes = {"combined_hash": current_combined_hash}
            save_hashes(new_hashes)
            
            # Show final stats
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
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
                
            finally:
                conn.close()
        else:
            print("❌ Import failed")
    else:
        print(f"\n✅ Database ready! Use: python app.py")

if __name__ == "__main__":
    main()
