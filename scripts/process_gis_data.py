#!/usr/bin/env python3
"""Process GIS data to extract latitude/longitude for each property.

This script searches for a shapefile ('.shp') within the extracted/text data
directories, loads it with GeoPandas, and attempts to map parcel/account IDs
to coordinates that can be stored in the SQLite database for distance queries.

Assumptions / Fallbacks:
1. The shapefile contains a unique parcel or account identifier. Common field
   names tried (case-insensitive): ['acct', 'account', 'ACCOUNT', 'ACCT',
   'prop_id', 'propid', 'OBJECTID']
2. If more than one candidate field exists, the first with non-null values is used.
3. Coordinates are stored as WGS84 (EPSG:4326). If the source CRS differs, it
   is re-projected.
4. A table `property_geo(acct TEXT PRIMARY KEY, latitude REAL, longitude REAL)`
   is created / updated.

Run:
  python scripts/process_gis_data.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

try:
    import geopandas as gpd  # type: ignore
except ImportError as e:  # pragma: no cover
    print("❌ geopandas not installed. Add it to requirements and reinstall.")
    raise

BASE_DIR = Path(__file__).resolve().parent.parent
TEXT_DIR = BASE_DIR / "text_files"
GIS_EXPORT_DIR = BASE_DIR / "Exports" / "GIS"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "database.sqlite"

def find_shapefile() -> Optional[Path]:
    candidates = list(TEXT_DIR.rglob("*.shp")) + list(GIS_EXPORT_DIR.rglob("*.shp"))
    if not candidates:
        print("No shapefile found under text_files/ or Exports/GIS/. Run extract_gis_nested.py.")
        return None
    shp = max(candidates, key=lambda p: p.stat().st_size)
    print(f"Using shapefile: {shp}")
    return shp

def load_geodata(shp: Path):
    gdf = gpd.read_file(shp)
    print(f"Loaded {len(gdf):,} geometries. Columns: {list(gdf.columns)}")
    return gdf

def choose_account_column(gdf) -> Optional[str]:
    # Extended list includes common parcel identifiers used by HCAD GIS datasets
    preferred = [
        "acct", "account", "ACCOUNT", "ACCT",
        "prop_id", "propid", "PROP_ID",
        "parcelid", "ParcelID", "PARCELID", "parcel_id", "Parcel_ID",
        "OBJECTID"
    ]
    lower_map = {c.lower(): c for c in gdf.columns}
    for cand in preferred:
        if cand.lower() in lower_map:
            col = lower_map[cand.lower()]
            if gdf[col].notnull().sum() > 0:
                print(f"Using account column: {col}")
                return col
    print("No suitable account identifier column found.")
    return None

def ensure_wgs84(gdf):
    try:
        if gdf.crs is None:
            print("⚠️  Shapefile CRS unknown; assuming EPSG:4326 (already lat/lon).")
            return gdf
        if gdf.crs.to_epsg() != 4326:
            print(f"Re-projecting from {gdf.crs} to EPSG:4326 ...")
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except Exception as e:  # pragma: no cover
        print(f"CRS handling issue: {e}; continuing without reprojection.")
        return gdf

def write_sqlite(rows):
    if not DB_PATH.exists():
        print(f"SQLite DB not found at {DB_PATH}. Run extract_data.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS property_geo (acct TEXT PRIMARY KEY, latitude REAL, longitude REAL)")
    cur.executemany("INSERT OR REPLACE INTO property_geo(acct, latitude, longitude) VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"Inserted/updated {len(rows):,} coordinate rows.")

def main():
    shp = find_shapefile()
    if not shp:
        return
    gdf = load_geodata(shp)
    acct_col = choose_account_column(gdf)
    if not acct_col:
        return
    gdf = ensure_wgs84(gdf)
    geom = gdf.geometry
    reps = geom.representative_point()
    rows = []
    for acct, point in zip(gdf[acct_col], reps):  # type: ignore
        if acct is None or point is None:
            continue
        try:
            lat, lon = float(point.y), float(point.x)  # type: ignore[attr-defined]
            rows.append((str(acct), lat, lon))
        except Exception:
            continue
    if not rows:
        print("No coordinate rows extracted.")
        return
    write_sqlite(rows)

if __name__ == "__main__":
    main()
