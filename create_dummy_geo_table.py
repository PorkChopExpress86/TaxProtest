import sqlite3
import random
import pandas as pd

def create_dummy_geo_table():
    """Create a dummy property_geo table with sample coordinates for testing purposes"""
    
    db_path = 'e:\\TaxProtest\\data\\database.sqlite'
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get a sample of real account numbers from the database
    cursor.execute("SELECT DISTINCT acct FROM real_acct LIMIT 1000")
    accounts = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Creating dummy geo data for {len(accounts)} properties...")
    
    # Generate dummy coordinates within Harris County bounds
    # Harris County, TX approximate bounds:
    # Latitude: 29.5 to 30.2
    # Longitude: -95.8 to -94.9
    
    geo_data = []
    for acct in accounts:
        lat = round(random.uniform(29.5, 30.2), 6)
        lon = round(random.uniform(-95.8, -94.9), 6)
        geo_data.append({
            'acct': str(acct),
            'latitude': lat,
            'longitude': lon
        })
    
    # Create DataFrame and insert into database
    df = pd.DataFrame(geo_data)
    df.to_sql('property_geo', conn, if_exists='replace', index=False)
    
    # Create an index for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)")
    conn.commit()
    
    print(f"✅ Created dummy property_geo table with {len(geo_data)} records")
    print("🗺️ Coordinates are within Harris County bounds for testing")
    print("⚠️ Note: These are dummy coordinates for testing. Replace with real data when available.")
    
    conn.close()

if __name__ == "__main__":
    create_dummy_geo_table()
