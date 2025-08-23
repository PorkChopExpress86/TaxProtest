import sqlite3
import pandas as pd
from pathlib import Path

# Path to the real parcels.csv file (update this if needed)
PARCELS_CSV = Path('extracted/gis/parcels.csv')
# Path to your main SQLite database
DB_PATH = Path('data/database.sqlite')

def import_parcels_to_property_geo():
    if not PARCELS_CSV.exists():
        print(f"parcels.csv not found at {PARCELS_CSV}")
        return
    
    # Read the parcels.csv file
    df = pd.read_csv(PARCELS_CSV, dtype={'HCAD_NUM': str, 'latitude': float, 'longitude': float})
    # Clean up column names and trim whitespace
    df['HCAD_NUM'] = df['HCAD_NUM'].str.strip()
    df = df.drop_duplicates(subset=['HCAD_NUM'])
    
    # Prepare DataFrame for SQLite
    df = df.rename(columns={'HCAD_NUM': 'acct'})[['acct', 'latitude', 'longitude']]
    
    # Connect to the main database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Create or replace the property_geo table
    cur.execute('DROP TABLE IF EXISTS property_geo')
    cur.execute('''
        CREATE TABLE property_geo (
            acct TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL
        )
    ''')
    
    # Insert data
    df.to_sql('property_geo', conn, if_exists='append', index=False)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)')
    conn.commit()
    conn.close()
    print(f"Imported {len(df)} records into property_geo table.")

if __name__ == "__main__":
    import_parcels_to_property_geo()
