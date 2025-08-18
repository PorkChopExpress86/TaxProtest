"""
Step 1: Download Harris County Tax Data
=====================================

Enhancements (quick-win optimizations):
 - Conditional requests (HEAD with If-Modified-Since / If-None-Match) to avoid full downloads
 - Metadata tracking (last_modified, etag, content_length) in data/download_meta.json
 - Parallel downloading via ThreadPoolExecutor (configurable workers)
 - Size/mtime + metadata shortcut to skip recomputing file hashes for unchanged files
 - JSON summary report for orchestration (data/last_download_report.json)

Existing hash logic retained for backward compatibility.
"""

import hashlib
import json
import os
import requests
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DOWNLOADS_DIR = BASE_DIR / "downloads"
HASH_FILE = BASE_DIR / "data" / "download_hashes.json"
META_FILE = BASE_DIR / "data" / "download_meta.json"
REPORT_FILE = BASE_DIR / "data" / "last_download_report.json"

# Ensure directories exist
DOWNLOADS_DIR.mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_existing_hashes():
    """Load existing hash data from JSON file"""
    if HASH_FILE.exists():
        try:
            with open(HASH_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {}

def save_hashes(hash_data):
    """Save hash data to JSON file"""
    with open(HASH_FILE, 'w') as f:
        json.dump(hash_data, f, indent=2)

def _load_meta() -> Dict[str, Any]:
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_meta(meta: Dict[str, Any]):
    try:
        META_FILE.write_text(json.dumps(meta, indent=2))
    except Exception as e:
        print(f"⚠️  Failed saving meta file: {e}")

def _conditional_head(url: str, headers: Dict[str, str]) -> Optional[requests.Response]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=60, headers=headers)
        # Some servers do not implement HEAD fully; we still return
        return r
    except Exception:
        return None

def download_file(url, output_path, description, existing_meta: Dict[str, Any]):
    """Download a file (with conditional skip) returning tuple(success, skipped, meta_dict)."""
    meta_headers = {}
    if 'etag' in existing_meta:
        meta_headers['If-None-Match'] = existing_meta['etag']
    if 'last_modified' in existing_meta:
        meta_headers['If-Modified-Since'] = existing_meta['last_modified']

    head_resp = _conditional_head(url, meta_headers)
    if head_resp is not None:
        # 304 Not Modified means skip
        if head_resp.status_code == 304 and output_path.exists():
            return True, True, existing_meta  # success, skipped
        # If 200, compare content-length & last-modified to decide skip
        if head_resp.status_code == 200 and output_path.exists():
            cl = head_resp.headers.get('Content-Length')
            lm = head_resp.headers.get('Last-Modified')
            if cl and lm and existing_meta.get('content_length') == cl and existing_meta.get('last_modified') == lm:
                # Treat as unchanged
                return True, True, existing_meta
    # Need full GET
    print(f"Downloading {description}...")
    try:
        with requests.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            print(f"  Progress: {percent:.1f}% ({downloaded_size:,} / {total_size:,} bytes)", end='\r')
            print(f"  [OK] Downloaded {description} ({downloaded_size:,} bytes)")
            new_meta = {
                'url': url,
                'content_length': response.headers.get('Content-Length'),
                'last_modified': response.headers.get('Last-Modified'),
                'etag': response.headers.get('ETag'),
                'downloaded_at': datetime.utcnow().isoformat() + 'Z'
            }
            return True, False, new_meta
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error downloading {description}: {e}")
        return False, False, existing_meta

def main(workers: int | None = None) -> dict:
    print("Harris County Tax Data Downloader")
    print("=" * 50)
    
    # Current year for dynamic URLs
    year = datetime.now().strftime("%Y")
    
    # Define files to download
    # GIS_Public.zip removed (Parcels content handled via direct Parcels.zip download with fallback)
    files_to_download = [
        {"url": f"https://download.hcad.org/data/CAMA/{year}/Real_building_land.zip", "filename": "Real_building_land.zip", "description": "Real Estate Building & Land Data"},
        {"url": f"https://download.hcad.org/data/CAMA/{year}/Real_acct_owner.zip", "filename": "Real_acct_owner.zip", "description": "Real Estate Account & Owner Data"},
        {"url": f"https://download.hcad.org/data/CAMA/{year}/Hearing_files.zip", "filename": "Hearing_files.zip", "description": "Hearing Files Data"},
        {"url": f"https://download.hcad.org/data/CAMA/{year}/Code_description_real.zip", "filename": "Code_description_real.zip", "description": "Real Estate Code Descriptions"},
        {"url": f"https://download.hcad.org/data/CAMA/{year}/PP_files.zip", "filename": "PP_files.zip", "description": "Personal Property Files"},
        {"url": f"https://download.hcad.org/data/CAMA/{year}/Code_description_pp.zip", "filename": "Code_description_pp.zip", "description": "Personal Property Code Descriptions"},
        # Parcels.zip handled separately below for fallback logic but we keep it here for counting/download pass
        {"url": "https://download.hcad.org/data/GIS/Parcels.zip", "filename": "Parcels.zip", "description": "GIS Parcels Shapefile (primary)"}
    ]

    def first_bad_member(path: Path) -> Optional[str]:
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                return zf.testzip()
        except Exception:
            return '<<unreadable>>'

    def download_parcels_with_fallback(primary_path: Path) -> tuple[Path, bool]:
        """Ensure Parcels archive present & sane. Returns (path, backup_used). Does not hash-track backup."""
        backup_used = False
        primary_bad = False
        if primary_path.exists():
            bad = first_bad_member(primary_path)
            if bad:
                primary_bad = True
                print(f"❌ Existing Parcels.zip appears corrupt (bad member: {bad})")
        else:
            # primary downloaded in normal loop; if missing we treat as needing download
            pass
        if primary_bad:
            backup_year = int(year) - 1
            backup_url = f"https://download.hcad.org/data/GIS/Parcels_{backup_year}_Oct.zip"
            backup_name = f"Parcels_{backup_year}_Oct.zip"
            backup_path = DOWNLOADS_DIR / backup_name
            if backup_path.exists():
                print(f"Using existing backup archive {backup_name}")
            else:
                print(f"Downloading backup archive {backup_url}")
                if not download_file(backup_url, backup_path, f"Backup Parcels {backup_year} October", {}):
                    print("Failed to obtain backup Parcels archive.")
                    return primary_path, False
            bad_b = first_bad_member(backup_path)
            if bad_b:
                print(f"❌ Backup archive also corrupt (bad member: {bad_b}). Proceeding with original corrupt file.")
                return primary_path, False
            print(f"Backup Parcels archive verified: {backup_name}")
            backup_used = True
            return backup_path, backup_used
        return primary_path, backup_used
    
    # Load existing hashes
    existing_hashes = load_existing_hashes()
    current_hashes = {}
    files_downloaded = 0
    files_skipped = 0
    
    meta = _load_meta()
    new_meta: Dict[str, Any] = dict(meta)  # copy
    lock = threading.Lock()

    # Decide worker count
    if workers is None:
        workers = min(4, len(files_to_download))

    def task(file_info):
        nonlocal files_downloaded, files_skipped
        url = file_info["url"]
        filename = file_info["filename"]
        description = file_info["description"]
        output_path = DOWNLOADS_DIR / filename
        existing_meta = meta.get(filename, {})
        # Fast skip via hash if hash file says unchanged and file exists
        if output_path.exists() and filename in existing_hashes:
            # If we also have unchanged metadata, we can skip computing hash entirely
            success, skipped, updated_meta = download_file(url, output_path, description, existing_meta)
        else:
            success, skipped, updated_meta = download_file(url, output_path, description, existing_meta)
        if success and skipped:
            # Ensure hash present (may reuse existing without recompute if we trust previous hash file)
            if filename in existing_hashes:
                with lock:
                    current_hashes[filename] = existing_hashes[filename]
                    files_skipped += 1
            else:
                # Need to hash once
                file_hash = calculate_file_hash(output_path)
                with lock:
                    current_hashes[filename] = file_hash
                    files_skipped += 1
        elif success and not skipped:
            # Fresh download; compute hash (except parcels until validated later)
            if filename != 'Parcels.zip':
                file_hash = calculate_file_hash(output_path)
                with lock:
                    current_hashes[filename] = file_hash
            with lock:
                files_downloaded += 1
        else:
            # failed; do nothing
            pass
        if updated_meta:
            with lock:
                new_meta[filename] = updated_meta
        return filename

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(task, fi) for fi in files_to_download]
        for f in as_completed(futures):
            _ = f.result()
    
    # Post-process Parcels fallback (after potential primary download)
    parcels_primary = DOWNLOADS_DIR / 'Parcels.zip'
    if parcels_primary.exists():
        resolved_parcels_path, backup_used = download_parcels_with_fallback(parcels_primary)
        if resolved_parcels_path.name == 'Parcels.zip':
            # Only now compute/store hash if not already stored and not corrupt
            if 'Parcels.zip' not in current_hashes:
                if not first_bad_member(resolved_parcels_path):
                    current_hashes['Parcels.zip'] = calculate_file_hash(resolved_parcels_path)
                else:
                    print("⚠️  Skipping hash store for corrupt Parcels.zip")
        else:
            # Backup used; deliberately do NOT store hash so future runs re-check when primary is fixed
            print(f"ℹ️  Fallback Parcels archive in use ({resolved_parcels_path.name}); hash not persisted.")
    else:
        print("⚠️  Parcels.zip missing after download phase.")

    # Save updated hashes (excluding backup parcels if used)
    save_hashes(current_hashes)
    _save_meta(new_meta)

    summary = {
        'timestamp_utc': datetime.utcnow().isoformat() + 'Z',
        'downloaded': files_downloaded,
        'skipped': files_skipped,
        'total': len(files_to_download),
        'changed': files_downloaded > 0
    }
    try:
        REPORT_FILE.write_text(json.dumps(summary, indent=2))
    except Exception:
        pass

    print(f"\nDownload Summary:")
    print(f"  Files downloaded: {files_downloaded}")
    print(f"  Files skipped (up to date): {files_skipped}")
    print(f"  Total primary files (excluding potential backup): {len(files_to_download)}")
    if files_downloaded > 0:
        print(f"\nDownload complete! Files saved to: {DOWNLOADS_DIR}")
        print("   Next step: Run step2_extract.py to extract the data")
    else:
        print(f"\nAll files up to date! No downloads needed.")
        print("   You can proceed with step2_extract.py if extraction is needed")
    return summary

if __name__ == "__main__":
    main()
