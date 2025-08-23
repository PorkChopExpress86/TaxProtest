"""
Step 2: Extract Harris County Tax Data
=====================================

This script extracts ZIP files downloaded in step 1 and tracks extraction
hashes to avoid unnecessary re-extraction.
"""

import hashlib
import json
import os
import zipfile
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DOWNLOADS_DIR = BASE_DIR / "downloads"
EXTRACTED_DIR = BASE_DIR / "extracted"
TEXT_FILES_DIR = BASE_DIR / "text_files"
HASH_FILE = BASE_DIR / "data" / "extraction_hashes.json"
SUMMARY_FILE = BASE_DIR / "data" / "last_extraction_report.json"

# Debug toggle: disable Parcels.zip CRC integrity enforcement during development
ENABLE_PARCELS_INTEGRITY_CHECK = False

# Ensure directories exist
EXTRACTED_DIR.mkdir(exist_ok=True)
TEXT_FILES_DIR.mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_existing_hashes():
    """Load existing extraction hash data from JSON file"""
    if HASH_FILE.exists():
        try:
            with open(HASH_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {}

def save_hashes(hash_data):
    """Save extraction hash data to JSON file"""
    with open(HASH_FILE, 'w') as f:
        json.dump(hash_data, f, indent=2)

def extract_zip_file(zip_path, extract_to, target_files=None):
    """Extract specific files from a ZIP archive"""
    extracted_files = []
    # Try pyzipper first (if installed) for potentially more tolerant extraction
    try_pyzipper = True
    pyzipper_available = False
    try:
        import pyzipper  # type: ignore
        pyzipper_available = True
    except Exception:
        try_pyzipper = False
    
    try:
        if try_pyzipper and pyzipper_available:
            try:
                with pyzipper.AESZipFile(zip_path, 'r') as zip_ref:  # works for normal zips too
                    file_list = zip_ref.namelist()
                    if target_files:
                        for file_name in file_list:
                            if any(target in file_name for target in target_files):
                                print(f"    (pyzipper) Extracting: {file_name}")
                                zip_ref.extract(file_name, extract_to)
                                extracted_files.append(file_name)
                    else:
                        print(f"    (pyzipper) Extracting all files...")
                        zip_ref.extractall(extract_to)
                        extracted_files = file_list
            except Exception as e:
                print(f"    ⚠️  pyzipper extraction failed ({e}); falling back to zipfile module")
        if not extracted_files:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                if target_files:
                    # Extract only specific files
                    for file_name in file_list:
                        if any(target in file_name for target in target_files):
                            print(f"    Extracting: {file_name}")
                            zip_ref.extract(file_name, extract_to)
                            extracted_files.append(file_name)
                else:
                    # Extract all files
                    print(f"    Extracting all files...")
                    zip_ref.extractall(extract_to)
                    extracted_files = file_list
                
    except zipfile.BadZipFile:
        try:
            import zipfile as _zf
            if _zf.is_zipfile(zip_path):
                with _zf.ZipFile(zip_path, 'r') as zr:
                    file_list = zr.namelist()
                    if target_files:
                        for file_name in file_list:
                            if any(target in file_name for target in target_files):
                                print(f"    Extracting (retry): {file_name}")
                                zr.extract(file_name, extract_to)
                                extracted_files.append(file_name)
                    else:
                        print("    Extracting all files (retry)...")
                        zr.extractall(extract_to)
                        extracted_files = file_list
                    print(f"    ✅ Extracted on retry {len(extracted_files)} files")
                    return extracted_files
        except Exception as ie:
            print(f"    ❌ Retry extraction failed for {zip_path.name}: {ie}")
        print(f"    ❌ Error: {zip_path.name} is not a valid ZIP file")
        return []
    except Exception as e:
        print(f"    ❌ Error extracting {zip_path.name}: {e}")
        return []
    
    return extracted_files

def _test_zip_first_bad_member(zip_path: Path) -> Optional[str]:
    """Return first bad member name if CRC fails; None if OK; '<<unreadable>>' if cannot open."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            return zf.testzip()
    except Exception:
        return '<<unreadable>>'

def _download_backup_parcels(backup_year: int, downloads_dir: Path) -> Optional[Path]:
    """Download previous year's October Parcels archive as fallback. Returns path or None."""
    try:
        import requests  # lazy import
    except ImportError:
        print("    ⚠️  'requests' not installed; cannot download backup parcels archive.")
        return None
    url = f"https://download.hcad.org/data/GIS/Parcels_{backup_year}_Oct.zip"
    dest = downloads_dir / f"Parcels_{backup_year}_Oct.zip"
    if dest.exists():
        print(f"    ↪️  Backup archive already present: {dest.name}")
    else:
        print(f"    🌐 Downloading backup parcels archive: {url}")
        try:
            with requests.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            print(f"    ❌ Failed to download backup archive: {e}")
            return None
    bad = _test_zip_first_bad_member(dest)
    if bad:
        print(f"    ❌ Backup archive appears corrupt (bad member: {bad}).")
        return None
    print(f"    ✅ Backup archive verified: {dest.name}")
    return dest

def verify_zip_integrity(zip_path: Path) -> bool:
    """Return True if the ZIP passes a basic integrity (CRC) test, else False.

    Uses ZipFile.testzip() which returns the first bad file name or None if all good.
    Large corrupt GIS archives have been observed (notably Parcels.zip); catching early lets us
    trigger a clean re-download instead of producing partial shapefiles / truncated DBF reads.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad = zf.testzip()
            if bad is not None:
                print(f"    ❌ ZIP integrity failed: first bad member '{bad}' in {zip_path.name}")
                return False
        return True
    except zipfile.BadZipFile:
        print(f"    ❌ ZIP integrity failed: {zip_path.name} is not a valid ZIP file")
        return False
    except Exception as e:
        print(f"    ⚠️  ZIP integrity check error for {zip_path.name}: {e}")
        return False

def extract_nested_parcels_archives(root: Path):
    """Find and extract any nested Parcels*.zip archives under root that may contain the shapefile.

    Some distributions wrap the actual Parcels shapefile inside a directory structure or another zip.
    We scan for zip files whose names contain 'Parcels' (case-insensitive) and that have not yet been
    extracted (i.e., we don't already see Parcels.shp alongside a DBF at the sibling path)."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if fname.lower().startswith('parcels') and fname.lower().endswith('.zip'):
                nested_zip = Path(dirpath) / fname
                try:
                    with zipfile.ZipFile(nested_zip, 'r') as zf:
                        names = zf.namelist()
                        # Only extract if it actually contains a Parcels.shp component
                        if any(n.lower().endswith('parcels.shp') for n in names):
                            print(f"  🔎 Extracting nested archive {nested_zip} ({len(names)} entries)")
                            zf.extractall(Path(dirpath))
                            count += 1
                except Exception as e:
                    print(f"  ⚠️  Failed to extract nested {nested_zip.name}: {e}")
    if count:
        print(f"  ✅ Extracted {count} nested Parcels archive(s)")
    return count

def fallback_external_extract(zip_path: Path, extract_to: Path) -> bool:
    """Attempt extraction using external utilities (PowerShell Expand-Archive, then 7-Zip).

    Returns True if any method succeeds, else False.
    """
    extract_to.mkdir(parents=True, exist_ok=True)

    # 1. PowerShell Expand-Archive (built-in on Windows)
    if os.name == 'nt':
        ps_cmd = [
            'powershell', '-NoLogo', '-NonInteractive', '-Command',
            f"Try {{ Expand-Archive -LiteralPath '{zip_path}' -DestinationPath '{extract_to}' -Force -ErrorAction Stop; Write-Host 'Expand-Archive success' }} Catch {{ Write-Host 'Expand-Archive failed:' $_.Exception.Message; exit 1 }}"
        ]
        try:
            print("    �️  Fallback: PowerShell Expand-Archive...")
            r = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0:
                print("        ✅ Expand-Archive succeeded")
                return True
            else:
                print(f"        ❌ Expand-Archive failed (code {r.returncode}): {r.stderr.strip() or r.stdout.strip()}")
        except Exception as e:
            print(f"        ⚠️  Expand-Archive exception: {e}")

    # 2. 7-Zip if available
    seven_zip_paths = [
        Path('C:/Program Files/7-Zip/7z.exe'),
        Path('C:/Program Files (x86)/7-Zip/7z.exe'),
        Path('7z.exe')
    ]
    seven_zip = next((p for p in seven_zip_paths if p.exists()), None)
    if seven_zip:
        try:
            print("    🛠️  Fallback: 7-Zip extraction...")
            cmd = [str(seven_zip), 'x', '-y', f'-o{extract_to}', str(zip_path)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0:
                print("        ✅ 7-Zip extraction succeeded")
                return True
            else:
                print(f"        ❌ 7-Zip failed (code {r.returncode})")
        except Exception as e:
            print(f"        ⚠️  7-Zip exception: {e}")

    return False

def unzip_parcel_data(src_dir: Path, dst_dir: Path) -> bool:
    """Replicate other project's unzip_parcel_data: walk src_dir, find Parcels.zip, extract all to dst_dir.

    Returns True if extraction occurred, else False.
    """
    found = False
    for root, dirs, files in os.walk(src_dir):
        for name in files:
            if name == "Parcels.zip":
                zip_path = Path(root) / name
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        print(f"    Extracting all (unzip_parcel_data): {zip_path}")
                        zf.extractall(dst_dir)
                        found = True
                        return True
                except Exception as e:
                    print(f"    ❌ unzip_parcel_data failed for {zip_path.name}: {e}")
                    return False
    if not found:
        print("    ⚠️ unzip_parcel_data did not find Parcels.zip under downloads directory")
    return False

def main():
    print("Harris County Tax Data Extractor")
    print("=" * 50)
    
    # Define extraction rules for each ZIP file
    extraction_rules = {
        "Real_building_land.zip": {
            "target_files": ["building_res.txt", "land.txt", "fixtures.txt", "extra_features.txt"],
            "description": "Building & Land Data"
        },
        "Real_acct_owner.zip": {
            "target_files": ["real_acct.txt", "owners.txt"], 
            "description": "Account & Owner Data"
        },
        "Hearing_files.zip": {
            "target_files": ["arb_hearings_real.txt", "arb_protest_real.txt"],
            "description": "Hearing Files"
        },
        "Code_description_real.zip": {
            "target_files": ["desc_r_01_state_class.txt", "desc_r_02_building_type_code.txt", 
                           "desc_r_03_building_style.txt", "desc_r_04_building_class.txt",
                           "desc_r_05_building_data_elements.txt", "desc_r_06_structural_element_type.txt",
                           "desc_r_07_quality_code.txt", "desc_r_08_pgi_category.txt"],
            "description": "Real Estate Code Descriptions"
        },
        "PP_files.zip": {
            "target_files": ["t_pp_c.txt", "t_pp_l.txt"],  # Personal property files 
            "description": "Personal Property & Features"  
        },
        "Code_description_pp.zip": {
            "target_files": None,  # Extract all
            "description": "Personal Property Code Descriptions"
        },
        "GIS_Public.zip": {
            # Extract all GIS data to ensure complete shapefile set (some zips nest shapefiles differently)
            "target_files": None,
            "description": "GIS Parcels & Layers (full extract for geopandas)"
        },
        "Parcels.zip": {
            # Extract ALL contents of Parcels.zip (full archive required)
            "target_files": None,
            "description": "Standalone Parcels Shapefile (full archive)"
        }
    }
    
    # Load existing extraction hashes  
    existing_hashes = load_existing_hashes()
    current_hashes = {}
    files_extracted = 0
    files_skipped = 0
    
    # Track whether GIS zip content changed so we know to rebuild parcels.csv
    gis_zip_changed = False

    for zip_filename, rules in extraction_rules.items():
        zip_path = DOWNLOADS_DIR / zip_filename
        
        if not zip_path.exists():
            print(f"⚠️  {zip_filename} not found in downloads directory")
            continue

        # Parcels.zip special handling: always probe for corruption & offer automatic fallback to previous October archive.
        parcels_corrupt_detected = False
        backup_used = False
        original_name = zip_filename
        if zip_filename == "Parcels.zip":
            bad_member = _test_zip_first_bad_member(zip_path)
            if bad_member:  # Corrupt or unreadable
                parcels_corrupt_detected = True
                print(f"[ERROR] Detected possible corruption in Parcels.zip (bad member: {bad_member}).")
                backup_year = datetime.utcnow().year - 1
                backup_zip = _download_backup_parcels(backup_year, DOWNLOADS_DIR)
                if backup_zip:
                    print(f"[INFO] Using fallback backup archive {backup_zip.name}")
                    zip_path = backup_zip
                    zip_filename = backup_zip.name  # note: we intentionally do NOT hash-track fallback yet
                    backup_used = True
                else:
                    # Last resort: attempt external fallback extraction on corrupt archive (may yield geometry only)
                    if ENABLE_PARCELS_INTEGRITY_CHECK:
                        print("    [WARN] Integrity enforcement is on; external fallback attempt...")
                        extract_to_tmp = EXTRACTED_DIR / "gis"
                        success = fallback_external_extract(zip_path, extract_to_tmp)
                        if success:
                            print("    [OK] External fallback extraction succeeded (data may still be incomplete).")
                            gis_zip_changed = True
                        else:
                            print("    [ERROR] Unable to extract Parcels.zip; skipping parcel centroid generation this run.")
                            continue
                    else:
                        print("    [WARN] Proceeding without usable attributes (hash tracking for fallback not yet enabled).")
            else:
                if ENABLE_PARCELS_INTEGRITY_CHECK:
                    print("[INFO] Parcels.zip integrity verified (CRC pass)")
                else:
                    print("[INFO] Parcels.zip basic CRC pass (integrity enforcement disabled)")
            
        # Calculate current ZIP hash
        zip_hash = calculate_file_hash(zip_path)
        
        # Check if we need to extract
        should_extract = True
        if zip_filename in existing_hashes and existing_hashes[zip_filename] == zip_hash and not parcels_corrupt_detected:
            # Extra safety: if this archive is supposed to provide specific text outputs but they are missing, force re-extract.
            missing_required = False
            if zip_filename == 'Real_acct_owner.zip':
                # expect real_acct.txt & owners.txt
                for expect in ('real_acct.txt','owners.txt'):
                    if not (TEXT_FILES_DIR / expect).exists():
                        missing_required = True
                        break
            elif zip_filename == 'Real_building_land.zip':
                for expect in ('building_res.txt','land.txt'):
                    if not (TEXT_FILES_DIR / expect).exists():
                        missing_required = True
                        break
            elif zip_filename == 'PP_files.zip':
                for expect in ('t_pp_c.txt','t_pp_l.txt'):
                    if not (TEXT_FILES_DIR / expect).exists():
                        missing_required = True
                        break
            if missing_required:
                print(f"[INFO] Required extracted file(s) missing for {zip_filename}; forcing re-extract.")
            else:
                print(f"[SKIP] {rules['description']} (already extracted, hash matches)")
                current_hashes[zip_filename] = zip_hash
                should_extract = False
                files_skipped += 1
        else:
            if zip_filename in existing_hashes:
                print(f"[INFO] ZIP file changed for {rules['description']}, re-extracting...")
            else:
                print(f"[EXTRACT] {rules['description']}...")
        
        if should_extract:
            # Determine extraction destination
            if zip_filename in ("GIS_Public.zip", "Parcels.zip") or (backup_used and zip_filename.endswith('_Oct.zip')):
                extract_to = EXTRACTED_DIR / "gis"
                extract_to.mkdir(exist_ok=True)
            else:
                extract_to = TEXT_FILES_DIR

            # Extract files
            extracted_files = extract_zip_file(zip_path, extract_to, rules['target_files'])

            if extracted_files:
                print(f"    [OK] Extracted {len(extracted_files)} files")
                # NOTE: We intentionally skip adding hash for backup/fallback parcels archives so that
                # future runs will re-check integrity until a fixed current-year Parcels.zip replaces it.
                if not (backup_used and zip_filename.endswith('_Oct.zip')):
                    current_hashes[zip_filename] = zip_hash
                files_extracted += 1
                if zip_filename in ("GIS_Public.zip", "Parcels.zip") or (backup_used and zip_filename.endswith('_Oct.zip')):
                    gis_zip_changed = True
            else:
                print(f"    [WARN] No files extracted from {zip_filename}")
        else:
            if zip_filename in ("GIS_Public.zip", "Parcels.zip"):
                gis_zip_changed = False  # unchanged
    
    # After extraction, attempt to build parcels.csv (centroids) from shapefile similar to reference project
    try:
        parcels_csv_path = EXTRACTED_DIR / "gis" / "parcels.csv"
        # Only rebuild if GIS zip changed or parcels.csv missing
        if gis_zip_changed or not parcels_csv_path.exists():
            print("\n[INFO] Generating parcels.csv (parcel centroids)...")
            try:
                import geopandas as gpd
                from shapely.geometry import shape
            except ImportError:
                print("  [WARN] geopandas not installed; skipping parcel centroid generation.")
            else:
                # Common shapefile path pattern
                shape_dir = EXTRACTED_DIR / "gis"
                # First, attempt to extract any nested Parcels archives if present
                extract_nested_parcels_archives(shape_dir)
                # Attempt to locate Parcels.shp anywhere under gis directory (covers GIS_Public or standalone Parcels.zip)
                shp_candidates = []
                for root, dirs, files in os.walk(shape_dir):
                    for f in files:
                        if f.lower() == "parcels.shp":
                            shp_candidates.append(Path(root) / f)
                if not shp_candidates:
                    print("  [WARN] Parcels.shp not found under extracted/gis; skipping.")
                else:
                    shapefile_path = shp_candidates[0]
                    print(f"  [INFO] Using shapefile: {shapefile_path}")

                    def read_parcels(path: Path):
                        """Robust shapefile read attempting multiple engines & encodings."""
                        attempts = []
                        engines = [None, 'fiona']
                        encodings = [None, 'utf-8', 'latin-1', 'cp1252']
                        for eng in engines:
                            for enc in encodings:
                                try:
                                    kwargs = {}
                                    if eng:
                                        kwargs['engine'] = eng
                                    if enc:
                                        kwargs['encoding'] = enc
                                    gdf_local = gpd.read_file(path, **kwargs)
                                    return gdf_local
                                except Exception as e:
                                    attempts.append(f"engine={eng} enc={enc} err={e}")
                        raise RuntimeError("All shapefile read attempts failed:\n" + "\n".join(attempts))

                    try:
                        gdf = read_parcels(shapefile_path)
                    except Exception as e:
                        print(f"  [ERROR] Failed to read parcels shapefile: {e}")
                        gdf = None

                    if gdf is not None:
                        try:
                            from geopandas import GeoDataFrame as _GeoDataFrame
                            if not isinstance(gdf, _GeoDataFrame):
                                raise TypeError("Expected GeoDataFrame from read_parcels")
                            if gdf.crs is None:
                                raise ValueError("Shapefile CRS undefined.")
                            # Compare via string to avoid GeoPandas object direct boolean issues
                            if str(gdf.crs).upper() not in ("EPSG:4326", "WGS84", "EPSG:4326()"):
                                gdf = gdf.to_crs("EPSG:4326")
                            # Filter valid geometries
                            gdf = gdf[gdf.geometry.is_valid]
                            # Compute centroids (geometry.centroid warns on geographic CRS but acceptable for small area)
                            gdf["latitude"] = gdf.geometry.centroid.y
                            gdf["longitude"] = gdf.geometry.centroid.x
                            # Find account column
                            # Identify probable account column
                            acct_col = None
                            preferred_names = {"HCAD_NUM","ACCT","ACCOUNT","ACCT_NUM","PARCEL","PARCEL_ID"}
                            for col in gdf.columns:
                                if col.upper() in preferred_names:
                                    acct_col = col
                                    break
                            if acct_col is None:
                                # Heuristic: column with highest count of 10-15 digit numeric strings
                                best_col = None
                                best_score = 0
                                for col in gdf.columns:
                                    if col == 'geometry':
                                        continue
                                    series = gdf[col].astype(str).str.strip()
                                    digits = series.str.fullmatch(r"\d{10,15}")
                                    score = digits.sum()
                                    if score > best_score and score > 100:  # threshold to avoid random
                                        best_score = score
                                        best_col = col
                                acct_col = best_col
                            if acct_col is None:
                                raise ValueError("Account column not found (after heuristics). Columns: " + ",".join(gdf.columns))
                            df_out = gdf[[acct_col, "latitude", "longitude"]].copy()
                            df_out[acct_col] = df_out[acct_col].astype(str).str.replace(r"\D","", regex=True).str.zfill(13)
                            df_out = df_out.rename(columns={acct_col: "acct"})
                            df_out = df_out.drop_duplicates(subset=["acct"]).dropna(subset=["latitude", "longitude"])
                            # Persist minimal CSV
                            df_out.to_csv(parcels_csv_path, index=False)
                            print(f"  [OK] parcels.csv generated with {len(df_out):,} rows -> {parcels_csv_path}")
                        except Exception as e:
                            print(f"  [ERROR] Error generating parcels.csv: {e}")
        else:
            print("\n[INFO] Parcel centroids up to date (parcels.csv exists and GIS zip unchanged).")
    except Exception as e:
        print(f"[WARN] Unexpected error during parcel centroid generation: {e}")

    # Save updated hashes (after potential generation)
    save_hashes(current_hashes)
    
    print(f"\nExtraction Summary:")
    print(f"  Archives extracted: {files_extracted}")
    print(f"  Archives skipped (up to date): {files_skipped}")
    print(f"  Total archives: {len(extraction_rules)}")
    
    # List key extracted files
    key_files = [
        TEXT_FILES_DIR / "real_acct.txt",
        TEXT_FILES_DIR / "building_res.txt", 
        TEXT_FILES_DIR / "fixtures.txt",
        TEXT_FILES_DIR / "extra_features.txt",
        TEXT_FILES_DIR / "owners.txt"
    ]
    
    print(f"\nKey Files Status:")
    for file_path in key_files:
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {file_path.name} ({size_mb:.1f} MB)")
        else:
            print(f"  [MISSING] {file_path.name} (missing)")
    
    if files_extracted > 0:
        print(f"\nExtraction complete!")
        print("   Next step: Run step3_import.py to import data into SQLite")
    else:
        print(f"\nAll files up to date! No extraction needed.")
        print("   You can proceed with step3_import.py if database import is needed")

    # Write JSON summary for orchestrator
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "archives_extracted": files_extracted,
        "archives_skipped": files_skipped,
        "total_archives": len(extraction_rules),
        "changed": files_extracted > 0,
        "key_files_present": {kf.name: (kf.exists()) for kf in key_files}
    }
    try:
        SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    except Exception:
        pass

if __name__ == "__main__":
    main()
