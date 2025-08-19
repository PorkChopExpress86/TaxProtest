import os
import sqlite3
import pandas as pd
from pathlib import Path

try:  # Postgres URL detection
    from db import get_connection, wrap_cursor  # lightweight wrapper (handles both backends)
except Exception:  # pragma: no cover - defensive
    get_connection = None  # type: ignore
    wrap_cursor = None  # type: ignore

USING_POSTGRES = os.getenv("TAXPROTEST_DATABASE_URL", "").startswith("postgres")

# Try to import geopandas for shapefile support
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
EXTRACTED_DIR = BASE_DIR / "extracted"
DB_PATH = BASE_DIR / 'data' / 'database.sqlite'

# ------------------------ Postgres helper paths ------------------------

def _ensure_postgis(conn):  # pragma: no cover - simple DDL utility
    try:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        conn.commit()
    except Exception:
        try: conn.rollback()
        except Exception: pass
    finally:
        try: cur.close()
        except Exception: pass

def _replace_property_geo_postgres(df: pd.DataFrame):
    """Replace property_geo table in Postgres with lon/lat + geom.

    Uses COPY for speed; adds geometry column & GIST index.
    """
    if get_connection is None:
        raise RuntimeError("db.get_connection not available")
    with get_connection() as conn:  # type: ignore
        _ensure_postgis(conn)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS property_geo")
        cur.execute("CREATE TABLE property_geo (acct TEXT PRIMARY KEY, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geom geometry(Point,4326))")
        # COPY
        try:
            if hasattr(cur, 'copy'):  # psycopg3 fast path
                copy_cmd = "COPY property_geo (acct, latitude, longitude) FROM STDIN WITH (FORMAT csv, DELIMITER ',', NULL '', HEADER false)"
                import io, csv as _csv
                buf = io.StringIO()
                w = _csv.writer(buf, lineterminator='\n')
                for row in df[['acct','latitude','longitude']].itertuples(index=False):
                    w.writerow(row)
                buf.seek(0)
                cur.execute("BEGIN")
                try:
                    with cur.copy(copy_cmd) as cp:  # type: ignore[attr-defined]
                        for line in buf:
                            cp.write(line)
                except Exception:
                    cur.execute("ROLLBACK"); raise
                cur.execute("COMMIT")
            else:  # fallback executemany
                rows = list(df[['acct','latitude','longitude']].itertuples(index=False, name=None))
                cur.executemany("INSERT INTO property_geo (acct, latitude, longitude) VALUES (%s,%s,%s)", rows)
        except Exception as e:  # pragma: no cover - error logging path
            try: conn.rollback()
            except Exception: pass
            raise RuntimeError(f"COPY/insert into property_geo failed: {e}")
        # Populate geom
        try:
            cur.execute("UPDATE property_geo SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) WHERE longitude IS NOT NULL AND latitude IS NOT NULL")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_property_geo_geom ON property_geo USING GIST(geom)")
            conn.commit()
        finally:
            cur.close()

def install_geopandas():
    """Install geopandas and its dependencies"""
    import subprocess
    import sys
    
    try:
        print("📦 Installing geopandas for shapefile support...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "geopandas"])
        global GEOPANDAS_AVAILABLE
        GEOPANDAS_AVAILABLE = True
        print("✅ geopandas installed successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to install geopandas: {e}")
        return False

def load_geo_data():
    """
    Loads geographic data from the extracted GIS file into the SQLite database.
    It searches for the correct file within the 'gis' directory.
    """
    global GEOPANDAS_AVAILABLE
    
    print("🌎 Loading geographic data...")
    gis_dir = EXTRACTED_DIR / "gis"
    
    # Check for the extracted parcels directory first
    parcels_extracted_dir = gis_dir / "parcels_extracted" / "HCAD_PDATA" / "Parcels"
    
    if parcels_extracted_dir.exists():
        # Look for the shapefile
        shapefile_path = parcels_extracted_dir / "Parcels.shp"
        
        if shapefile_path.exists():
            print(f"✅ Found shapefile: {shapefile_path}")
            
            # Install geopandas if not available
            if not GEOPANDAS_AVAILABLE:
                if not install_geopandas():
                    print("❌ Cannot proceed without geopandas for shapefile support")
                    return
            
            # Import geopandas (fresh import after potential installation)
            import geopandas as gpd
            
            try:
                # Read the shapefile using geopandas with different encoding options
                print("📊 Loading shapefile data...")
                
                # Try different encodings for shapefile
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                gdf = None
                
                for encoding in encodings_to_try:
                    try:
                        print(f"🔄 Trying encoding: {encoding}")
                        gdf = gpd.read_file(shapefile_path, encoding=encoding)
                        print(f"✅ Successfully loaded with encoding: {encoding}")
                        break
                    except UnicodeDecodeError as e:
                        print(f"  ❌ Encoding {encoding} failed: {e}")
                        continue
                    except Exception as e:
                        print(f"  ❌ Error with encoding {encoding}: {e}")
                        continue
                
                if gdf is None:
                    print("❌ Could not read shapefile with any encoding")
                    return
                
                print(f"✅ Loaded {len(gdf)} parcel records")
                print(f"📋 Columns available: {list(gdf.columns)}")
                
                # Get the centroid coordinates
                print("🗺️ Computing parcel centroids...")
                gdf['centroid'] = gdf.geometry.centroid
                gdf['longitude'] = gdf.centroid.x
                gdf['latitude'] = gdf.centroid.y
                
                # Look for account column with flexible matching
                account_col = None
                possible_account_cols = ['HCAD_NUM', 'ACCOUNT', 'ACCT', 'PARCEL_ID', 'ACCOUNT_NUM']
                
                for col in possible_account_cols:
                    if col in gdf.columns:
                        account_col = col
                        print(f"✅ Found account column: {col}")
                        break
                
                if not account_col:
                    print(f"❌ No account column found. Available columns: {list(gdf.columns)}")
                    return
                
                # Create the dataframe for database import
                df = pd.DataFrame({
                    'acct': gdf[account_col].astype(str).str.strip(),
                    'latitude': gdf['latitude'],
                    'longitude': gdf['longitude']
                })
                
                # Remove any invalid coordinates
                df = df.dropna(subset=['latitude', 'longitude'])
                df = df[(df['latitude'] != 0) & (df['longitude'] != 0)]
                
                print(f"📊 Prepared {len(df)} valid parcel records for database")
                
                if USING_POSTGRES:
                    _replace_property_geo_postgres(df)
                    print(f"✅ Loaded {len(df)} geo rows into Postgres property_geo (with geom)")
                    return
                else:
                    # SQLite path
                    conn = sqlite3.connect(DB_PATH)
                    df.to_sql('property_geo', conn, if_exists='replace', index=False)
                    print(f"✅ Geographic data for {len(df)} properties loaded into 'property_geo' table.")
                    print("🔍 Creating index on 'property_geo' table...")
                    cursor = conn.cursor()
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)")
                    conn.commit()
                    print("✅ Index created successfully.")
                    conn.close()
                    return
                
            except Exception as e:
                print(f"❌ Error loading shapefile: {e}")
                import traceback
                traceback.print_exc()
                return
        else:
            print(f"❌ Shapefile not found at: {shapefile_path}")
    else:
        print(f"❌ Extracted parcels directory not found: {parcels_extracted_dir}")
        print("🔄 Attempting to extract Parcels.zip...")
        
        # Try to extract Parcels.zip if it exists
        parcels_zip = gis_dir / "Parcels.zip"
        if parcels_zip.exists():
            print(f"  Found Parcels.zip, attempting to extract...")
            try:
                import zipfile
                extract_dir = gis_dir / "parcels_extracted"
                with zipfile.ZipFile(parcels_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    print(f"  ✅ Extracted Parcels.zip to {extract_dir}")
                    
                    # Recursively call this function to process the extracted files
                    return load_geo_data()
                    
            except Exception as e:
                print(f"  ❌ Could not extract Parcels.zip: {e}")
        else:
            print(f"❌ Parcels.zip not found at: {parcels_zip}")
    
    # Fallback: try to find and load CSV/text files
    print("🔄 Falling back to text/CSV file search...")
    
    gis_file_path = None
    possible_files = ["parcels.txt", "parcels.csv", "gis_public.txt", "HCAD_PDATA.txt"]
    
    for root, _, files in os.walk(gis_dir):
        for f in files:
            if f.lower() in [pf.lower() for pf in possible_files]:
                potential_path = Path(root) / f
                # Skip the corrupted parcels.txt that's actually binary data
                if f.lower() == "parcels.txt" and potential_path.stat().st_size > 500000000:
                    print(f"  Skipping large binary parcels.txt file: {potential_path}")
                    continue
                gis_file_path = potential_path
                print(f"  Found GIS data file: {gis_file_path}")
                break
        if gis_file_path:
            break

    if not gis_file_path or not gis_file_path.exists():
        print(f"❌ Geographic data file not found in {gis_dir}")
        print("   Searched for: parcels.txt, parcels.csv, gis_public.txt, HCAD_PDATA.txt")
        print("   Available files:")
        for item in gis_dir.iterdir():
            print(f"     {item.name}")
        return

    try:
        # Read the GIS data using pandas, trying different formats
        df = None
        try:
            df = pd.read_csv(gis_file_path, on_bad_lines='warn', low_memory=False)
            print(f"  ✅ Read file as CSV with comma separator")
        except Exception:
            try:
                df = pd.read_csv(gis_file_path, sep=r'\t', engine='python', on_bad_lines='warn', low_memory=False)
                print(f"  ✅ Read file as TSV with tab separator")
            except Exception as e:
                print(f"  ❌ Could not read file: {e}")
                return

        if df is None or df.empty:
            print(f"❌ No data found in {gis_file_path}")
            return

        print(f"  📊 Loaded {len(df)} rows, columns: {list(df.columns)}")

        # Standardize column names (ACCT, latitude, longitude)
        df.columns = [str(col).upper().strip() for col in df.columns]
        
        rename_map = {
            'HCAD_NUM': 'acct',
            'PARCEL': 'acct',
            'ACCT': 'acct',
            'ACCOUNT': 'acct',
            'X': 'longitude',
            'Y': 'latitude',
            'LAT': 'latitude',
            'LON': 'longitude',
            'LONGITUDE': 'longitude',
            'LATITUDE': 'latitude'
        }
        df.rename(columns=rename_map, inplace=True)

        # Check for required columns
        required_cols = ['acct', 'latitude', 'longitude']
        if not all(col in df.columns for col in required_cols):
            print(f"❌ Missing required columns in {gis_file_path}.")
            print(f"   Required: {required_cols}")
            print(f"   Found: {list(df.columns)}")
            return

        # Keep only the necessary columns and ensure correct types
        df = df[required_cols]
        df['acct'] = df['acct'].astype(str).str.strip()
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df.dropna(subset=['latitude', 'longitude'], inplace=True)

        if df.empty:
            print(f"❌ No valid coordinate data found after cleaning")
            return

        if USING_POSTGRES:
            _replace_property_geo_postgres(df)
            print(f"✅ Loaded {len(df)} geo rows into Postgres property_geo (with geom)")
        else:
            conn = sqlite3.connect(DB_PATH)
            df.to_sql('property_geo', conn, if_exists='replace', index=False)
            print(f"✅ Geographic data for {len(df)} properties loaded into 'property_geo' table.")
            print("🔍 Creating index on 'property_geo' table...")
            cursor = conn.cursor()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)")
            conn.commit()
            print("✅ Index created successfully.")

    except Exception as e:
        print(f"❌ An error occurred while loading geographic data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    load_geo_data()
