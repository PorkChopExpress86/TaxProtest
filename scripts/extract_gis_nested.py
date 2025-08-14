"""Extract nested GIS component ZIP archives from GIS_Public.zip into Exports/GIS.

HCAD's GIS_Public.zip is a container of many smaller ZIP files (Parcels.zip, Lot.zip, etc.).
To make shapefiles available for the geocoding/enrichment step we need to:

1. Create Exports/GIS/ if it does not exist.
2. For each inner *.zip member inside GIS_Public.zip:
   - Write it to disk under Exports/GIS/<inner_zip_name>
   - Extract its contents into Exports/GIS/<stem>/
3. Skip extraction for any inner zip whose extracted folder already exists unless --force provided.
4. Report how many shapefiles (.shp) were extracted in total.

Usage:
  python scripts/extract_gis_nested.py              # normal (idempotent)
  python scripts/extract_gis_nested.py --force      # re-extract everything
"""
from __future__ import annotations
import argparse
import zipfile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
GIS_CONTAINER = BASE_DIR / "zipped_data" / "GIS_Public.zip"
TARGET_BASE = BASE_DIR / "Exports" / "GIS"


def extract_inner(force: bool = False) -> int:
    if not GIS_CONTAINER.exists():
        print(f"❌ Container not found: {GIS_CONTAINER}. Run download_extract.py first.")
        return 0
    TARGET_BASE.mkdir(parents=True, exist_ok=True)
    shp_count = 0
    with zipfile.ZipFile(GIS_CONTAINER) as outer:
        inner_zips = [n for n in outer.namelist() if n.lower().endswith('.zip')]
        if not inner_zips:
            print("⚠️ No inner zip members detected – container format may have changed.")
        for name in inner_zips:
            inner_bytes = outer.read(name)
            inner_zip_path = TARGET_BASE / name
            extract_dir = TARGET_BASE / Path(name).stem
            if extract_dir.exists() and not force:
                print(f"Skip {name} (already extracted). Use --force to re-extract.")
                for shp in extract_dir.rglob('*.shp'):
                    shp_count += 1
                continue
            inner_zip_path.write_bytes(inner_bytes)
            try:
                with zipfile.ZipFile(inner_zip_path) as inner_zip:
                    inner_zip.extractall(extract_dir)
                print(f"Extracted {name} -> {extract_dir.relative_to(BASE_DIR)}")
            except zipfile.BadZipFile:
                print(f"Bad inner zip (skipping): {name}")
                continue
            for shp in extract_dir.rglob('*.shp'):
                shp_count += 1
    return shp_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract nested GIS component ZIPs.")
    parser.add_argument('--force', action='store_true', help='Re-extract even if target folders exist')
    args = parser.parse_args(argv)
    count = extract_inner(force=args.force)
    print(f"Total shapefiles present: {count}")
    if count == 0:
        print("⚠️  No shapefiles found. Verify the structure of GIS_Public.zip.")
    else:
        print(f"✅ Extraction complete. Shapefiles are under {TARGET_BASE}")
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
