"""Rebuild the property_geo table from the full Parcels shapefile.

Loads every parcel record, extracts centroid latitude/longitude, normalizes
account numbers to 13-digit zero-padded strings, and writes to SQLite.

Usage:
  python rebuild_property_geo.py [--limit N] [--silent]

Options:
  --limit N   Only process first N rows (debug/testing)
  --silent    Suppress per-1k progress output
"""
from __future__ import annotations
import argparse, sys, sqlite3, os
from pathlib import Path

try:
    import geopandas as gpd  # type: ignore
except ImportError:
    print("geopandas not installed. Install with: pip install -r requirements-geo.txt", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DB_PATH = BASE_DIR / 'data' / 'database.sqlite'

SHAPE_CANDIDATES = [
    BASE_DIR / 'extracted' / 'gis' / 'HCAD_PDATA' / 'Parcels' / 'Parcels.shp',
    BASE_DIR / 'extracted' / 'gis' / 'parcels_extracted' / 'HCAD_PDATA' / 'Parcels' / 'Parcels.shp'
]

ACCOUNT_COL_PREFER = ['HCAD_NUM','ACCT','ACCOUNT','ACCT_NUM','PROP_ID']

def find_shapefile() -> Path:
    for p in SHAPE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("Could not locate Parcels.shp in expected extract paths.")

def detect_account_column(columns) -> str:
    upper_map = {c.upper(): c for c in columns}
    for pref in ACCOUNT_COL_PREFER:
        if pref in upper_map:
            return upper_map[pref]
    # Fallback: choose first column that looks numeric-like
    for c in columns:
        if 'ACCT' in c.upper() or 'HCAD' in c.upper():
            return c
    raise ValueError("No suitable account column found in parcels layer.")

def rebuild(limit: int | None, silent: bool):
    shp = find_shapefile()
    print(f"📂 Reading shapefile: {shp}")
    try:
        gdf = gpd.read_file(shp)
    except UnicodeDecodeError:
        # Retry via fiona driver explicitly
        try:
            gdf = gpd.read_file(shp, engine='fiona')
        except Exception as e:
            print(f"Failed reading shapefile with both default and fiona engines: {e}")
            raise
    if gdf.crs is None:
        raise ValueError("Shapefile has no CRS; cannot proceed.")
    if gdf.crs != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')
    # Keep only valid geometries
    gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid]
    acct_col = detect_account_column(gdf.columns)
    # Centroid coordinates
    gdf['latitude'] = gdf.geometry.centroid.y
    gdf['longitude'] = gdf.geometry.centroid.x
    subset = gdf[[acct_col,'latitude','longitude']].copy()
    if limit:
        subset = subset.head(limit)
    # Normalize account numbers
    subset[acct_col] = subset[acct_col].astype(str).str.strip().str.replace(r'[^0-9]','', regex=True).str.zfill(13)
    subset = subset.drop_duplicates(subset=[acct_col])
    total = len(subset)
    print(f"✅ Prepared {total:,} parcel coordinate rows (after cleaning & dedupe)")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS property_geo')
    cur.execute('CREATE TABLE property_geo (acct TEXT PRIMARY KEY, latitude REAL, longitude REAL)')
    batch = []
    inserted = 0
    for idx, (acct, lat, lon) in enumerate(subset.itertuples(index=False, name=None), 1):
        if not acct or len(acct) != 13:
            continue
        batch.append((acct, float(lat), float(lon)))
        if len(batch) >= 1000:
            cur.executemany('INSERT OR REPLACE INTO property_geo VALUES (?,?,?)', batch)
            inserted += len(batch)
            batch.clear()
            if not silent:
                print(f"  Inserted {inserted:,}/{total:,} ({inserted/total:0.1%})", end='\r')
    if batch:
        cur.executemany('INSERT OR REPLACE INTO property_geo VALUES (?,?,?)', batch)
        inserted += len(batch)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct)')
    conn.commit(); conn.close()
    if not silent:
        print()
    print(f"🎯 Finished inserting {inserted:,} property_geo rows.")

def main():
    parser = argparse.ArgumentParser(description='Rebuild property_geo from parcels shapefile')
    parser.add_argument('--limit', type=int, help='Process only first N rows (debug)')
    parser.add_argument('--silent', action='store_true', help='Reduce logging')
    args = parser.parse_args()
    rebuild(args.limit, args.silent)

if __name__ == '__main__':
    main()
