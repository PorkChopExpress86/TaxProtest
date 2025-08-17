"""Test script: Download only Parcels.zip, extract, build parcels.csv with lat/long.

Usage:
    python scripts/test_parcels_download_extract.py \
        --download-dir downloads_test \
        --extract-dir extracted_test \
        --output-csv parcels.csv

The script will:
  1. Download https://download.hcad.org/data/GIS/Parcels.zip (direct HTTP GET)
  2. Extract the archive fully into the extract directory
  3. Locate Parcels.shp (recursive search)
  4. Read the shapefile with geopandas (optionally pyogrio/fiona engines)
  5. Reproject to EPSG:4326 if needed
  6. Compute centroid latitude/longitude
  7. Detect an account column (preferred names or heuristic)
  8. Write a minimal CSV: acct, latitude, longitude (13‑digit zero padded acct)

Notes:
  * This is intentionally standalone for troubleshooting the corrupt Parcels.zip issue.
  * If the download is corrupt, extraction or shapefile reading will fail early.
  * For speed you can install pyogrio (optional) which geopandas can auto-use.
"""
from __future__ import annotations
import argparse
import io
import os
import sys
import time
import zipfile
import hashlib
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    import requests
except ImportError:
    print("requests required. Install with: pip install requests")
    sys.exit(1)

CURRENT_YEAR = datetime.utcnow().year
PRIMARY_URL = "https://download.hcad.org/data/GIS/Parcels.zip"  # always points to current release
BACKUP_YEAR = CURRENT_YEAR - 1
BACKUP_URL = f"https://download.hcad.org/data/GIS/Parcels_{BACKUP_YEAR}_Oct.zip"

# These will be set dynamically once a usable archive is selected
PARCELS_URL = PRIMARY_URL
DEFAULT_FILENAME = "Parcels.zip"


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024, user_agent: Optional[str] = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"⬇️  Downloading {url}\n    → {dest}")
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent
    with requests.get(url, stream=True, timeout=180, headers=headers) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        start = time.time()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    sys.stdout.write(f"\r    {downloaded/1e6:8.1f} MB / {total/1e6:8.1f} MB ({pct:5.1f}%)")
                else:
                    sys.stdout.write(f"\r    {downloaded/1e6:8.1f} MB")
                sys.stdout.flush()
        duration = time.time() - start
    sys.stdout.write("\n")
    print(f"    ✅ Download complete in {duration:.1f}s (avg {(downloaded/1e6)/duration:.2f} MB/s)")
    return dest


def extract_zip(zip_path: Path, extract_to: Path, strict_crc: bool = True) -> List[str]:
    print(f"📦 Extracting {zip_path.name} → {extract_to} (strict_crc={strict_crc})")
    extract_to.mkdir(parents=True, exist_ok=True)
    members: List[str] = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        bad = zf.testzip()
        if bad is not None:
            print(f"    ❌ CRC error on member: {bad}")
            if strict_crc:
                raise RuntimeError(f"Corrupt ZIP member: {bad}")
            else:
                print("    ⚠️  Continuing (will try to extract what we can, skipping bad member).")
        for info in zf.infolist():
            target = info.filename
            try:
                # If not strict, skip known bad member
                if not strict_crc and bad and target == bad:
                    print(f"    ⏭️  Skipping corrupt member {target}")
                    continue
                zf.extract(info, extract_to)
                members.append(target)
            except Exception as e:
                print(f"    ⚠️  Failed to extract {target}: {e}")
                if strict_crc:
                    raise
    print(f"    ✅ Extracted {len(members)} member(s) (some may be missing if corruption skipped)")
    return members


def find_parcels_shapefile(root: Path) -> Optional[Path]:
    candidates = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower() == "parcels.shp":
                candidates.append(Path(dirpath) / f)
    if not candidates:
        return None
    # Choose the largest accompanying .dbf size as heuristic for completeness
    def dbf_size(shp: Path) -> int:
        dbf = shp.with_suffix('.dbf')
        return dbf.stat().st_size if dbf.exists() else 0
    candidates.sort(key=dbf_size, reverse=True)
    return candidates[0]


def load_and_generate(shp_path: Path, output_csv: Path) -> int:
    print(f"🗺️  Reading shapefile: {shp_path}")
    import geopandas as gpd
    from geopandas import GeoDataFrame
    from typing import cast

    def try_read() -> GeoDataFrame:
        attempts = []
        engines = [None, 'fiona']  # pyogrio auto-handled by geopandas if installed
        encodings = [None, 'utf-8', 'latin-1', 'cp1252']
        for eng in engines:
            for enc in encodings:
                try:
                    kwargs = {}
                    if eng:
                        kwargs['engine'] = eng
                    if enc:
                        kwargs['encoding'] = enc
                    gdf_local = gpd.read_file(shp_path, **kwargs)
                    # geopandas.read_file returns a GeoDataFrame; cast for type checker
                    return cast(GeoDataFrame, gdf_local)
                except Exception as e:
                    attempts.append(f"engine={eng} enc={enc} err={e}")
        raise RuntimeError("All read attempts failed:\n" + "\n".join(attempts))

    gdf = try_read()

    if gdf.crs is None:
        raise ValueError("Shapefile CRS undefined")
    if str(gdf.crs).upper() not in ("EPSG:4326", "WGS84", "EPSG:4326()"):
        print(f"    Reprojecting {gdf.crs} → EPSG:4326")
        gdf = gdf.to_crs("EPSG:4326")

    # Clean / compute centroids (will drop invalid geometries)
    gdf = gdf[gdf.geometry.is_valid]
    # centroid on geographic is acceptable here for approximate location; for precision could transform to local projected CRS first.
    gdf["latitude"] = gdf.geometry.centroid.y
    gdf["longitude"] = gdf.geometry.centroid.x

    # Detect account column
    preferred = {"HCAD_NUM", "ACCT", "ACCOUNT", "ACCT_NUM", "PARCEL", "PARCEL_ID"}
    acct_col = None
    for col in gdf.columns:
        if col.upper() in preferred:
            acct_col = col
            break
    if acct_col is None:
        best_col = None
        best_score = 0
        for col in gdf.columns:
            if col == 'geometry':
                continue
            series = gdf[col].astype(str).str.strip()
            digits = series.str.fullmatch(r"\d{10,15}")
            score = digits.sum()
            if score > best_score and score > 100:  # threshold
                best_score = score
                best_col = col
        acct_col = best_col
    if acct_col is None:
        raise ValueError("Could not find an account/parcel id column.")

    df_out = gdf[[acct_col, 'latitude', 'longitude']].copy()
    df_out[acct_col] = (df_out[acct_col].astype(str)
                        .str.replace(r"\D", "", regex=True)
                        .str.zfill(13))
    df_out = df_out.rename(columns={acct_col: 'acct'})
    df_out = df_out.drop_duplicates(subset=['acct']).dropna(subset=['latitude', 'longitude'])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(output_csv, index=False)
    print(f"    ✅ Wrote {len(df_out):,} rows → {output_csv}")
    return len(df_out)


def random_user_agent() -> str:
    base = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/","Firefox/", "Safari/537.36"
    ]
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(80,120)}.0.{random.randint(1000,5000)}.{random.randint(10,150)} Safari/537.36"


def check_zip_integrity(path: Path) -> bool:
    """Return True if zip passes testzip() (no corrupt members)."""
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            return zf.testzip() is None
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and extract Parcels.zip, generate parcels.csv")
    parser.add_argument('--download-dir', default='downloads_test', help='Directory to store the downloaded zip')
    parser.add_argument('--extract-dir', default='extracted_test', help='Directory to extract the zip contents into')
    parser.add_argument('--output-csv', default='parcels.csv', help='Output CSV filename (placed in extract-dir unless absolute)')
    parser.add_argument('--skip-download', action='store_true', help='Skip download if Parcels.zip already present')
    parser.add_argument('--retries', type=int, default=1, help='Number of download attempts if corruption detected')
    parser.add_argument('--sleep', type=int, default=5, help='Seconds to sleep between retries')
    parser.add_argument('--no-crc', action='store_true', help='Attempt best-effort extraction even if CRC fails (may lose attributes)')
    parser.add_argument('--diagnose-only', action='store_true', help='Only download & report integrity/hash; skip extraction & CSV')
    parser.add_argument('--force-backup', action='store_true', help='Force using previous year October backup archive')
    parser.add_argument('--year', type=int, default=CURRENT_YEAR, help='Override current year (for testing future/backfill)')
    args = parser.parse_args()

    # Allow overriding dynamic year logic
    global PARCELS_URL, DEFAULT_FILENAME, BACKUP_YEAR, BACKUP_URL
    if args.year != CURRENT_YEAR:
        # Recompute backup with overridden year
        BACKUP_YEAR = args.year - 1
        BACKUP_URL = f"https://download.hcad.org/data/GIS/Parcels_{BACKUP_YEAR}_Oct.zip"

    selected_is_backup = False
    # Decide which URL to attempt first (unless forced backup)
    if args.force_backup:
        PARCELS_URL = BACKUP_URL
        DEFAULT_FILENAME = f"Parcels_{BACKUP_YEAR}_Oct.zip"
        selected_is_backup = True
        print(f"🔁 Forcing backup archive: {PARCELS_URL}")
    else:
        PARCELS_URL = PRIMARY_URL
        DEFAULT_FILENAME = "Parcels.zip"

    download_dir = Path(args.download_dir)
    extract_dir = Path(args.extract_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    zip_path = download_dir / DEFAULT_FILENAME

    def perform_download(target_url: str, target_path: Path, retries: int) -> tuple[bool, str]:
        attempt = 0
        hashes: List[str] = []
        while True:
            attempt += 1
            if args.skip_download and target_path.exists() and attempt == 1:
                print(f"⚠️  Skipping download (existing {target_path.name})")
            else:
                ua = random_user_agent()
                download_file(target_url + (f"?t={int(time.time())}" if attempt>1 else ''), target_path, user_agent=ua)
            h = sha256sum(target_path)
            hashes.append(h)
            print(f"    🔐 SHA256: {h}")
            if attempt >= retries:
                break
            if len(hashes) >= 2 and hashes[-1] != hashes[-2]:
                print("    ✅ Hash changed from previous attempt; proceeding with last download")
                break
            else:
                print(f"    ⏳ Hash identical to previous attempt. Retry {attempt}/{retries} done.")
                if attempt < retries:
                    time.sleep(args.sleep)
        stable = len(set(hashes)) == 1
        return stable, hashes[-1]

    # Download selected archive (primary or forced backup)
    stable, last_hash = perform_download(PARCELS_URL, zip_path, args.retries)
    if not selected_is_backup:
        # Test integrity; if corrupt try backup
        if not check_zip_integrity(zip_path):
            print("❌ Primary Parcels.zip appears corrupt (CRC failure). Attempting backup year archive...")
            # Switch to backup
            PARCELS_URL = BACKUP_URL
            DEFAULT_FILENAME = f"Parcels_{BACKUP_YEAR}_Oct.zip"
            zip_path = download_dir / DEFAULT_FILENAME
            stable_backup, last_hash_b = perform_download(PARCELS_URL, zip_path, args.retries)
            if not check_zip_integrity(zip_path):
                print("❌ Backup archive also failed integrity. Aborting.")
                sys.exit(1)
            else:
                print(f"✅ Using backup archive {DEFAULT_FILENAME} (year {BACKUP_YEAR})")
                selected_is_backup = True
        else:
            print("✅ Primary archive passed integrity check.")

    if args.diagnose_only:
        print("🔍 Diagnose-only mode complete.")
        return

    try:
        extract_zip(zip_path, extract_dir, strict_crc=not args.no_crc)
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        if not args.no_crc:
            print("   Tip: re-run with --no-crc to attempt partial extraction (attributes may be unusable).")
        sys.exit(1)

    shp_path = find_parcels_shapefile(extract_dir)
    if not shp_path:
        print("❌ Parcels.shp not found after extraction")
        print("   Partial extraction may have skipped required members. If CRC corruption persists, source file replacement is needed.")
        sys.exit(1)

    # Resolve output CSV path
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute():
        output_csv = extract_dir / output_csv

    try:
        load_and_generate(shp_path, output_csv)
    except Exception as e:
        print(f"❌ Failed to generate parcels.csv: {e}")
        sys.exit(1)

    print("\n✅ Completed test parcels extraction & CSV generation.")


if __name__ == '__main__':
    main()
