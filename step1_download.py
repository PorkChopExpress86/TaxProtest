"""
Step 1: Download Harris County Tax Data
=====================================

This script downloads the required ZIP files from Harris County and tracks
their hashes to avoid unnecessary re-downloading.
"""

import hashlib
import json
import os
import requests
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DOWNLOADS_DIR = BASE_DIR / "downloads"
HASH_FILE = BASE_DIR / "data" / "download_hashes.json"

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

def download_file(url, output_path, description):
    """Download a file with progress indication"""
    print(f"Downloading {description}...")
    try:
        response = requests.get(url, stream=True)
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
        
        print(f"  ✅ Downloaded {description} ({downloaded_size:,} bytes)")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error downloading {description}: {e}")
        return False

def main():
    print("🏠 Harris County Tax Data Downloader")
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
                print(f"🔁 Using existing backup archive {backup_name}")
            else:
                print(f"🔁 Downloading backup archive {backup_url}")
                if not download_file(backup_url, backup_path, f"Backup Parcels {backup_year} October"):
                    print("🛑 Failed to obtain backup Parcels archive.")
                    return primary_path, False
            bad_b = first_bad_member(backup_path)
            if bad_b:
                print(f"❌ Backup archive also corrupt (bad member: {bad_b}). Proceeding with original corrupt file.")
                return primary_path, False
            print(f"✅ Backup Parcels archive verified: {backup_name}")
            backup_used = True
            return backup_path, backup_used
        return primary_path, backup_used
    
    # Load existing hashes
    existing_hashes = load_existing_hashes()
    current_hashes = {}
    files_downloaded = 0
    files_skipped = 0
    
    for file_info in files_to_download:
        url = file_info["url"]
        filename = file_info["filename"] 
        description = file_info["description"]
        output_path = DOWNLOADS_DIR / filename
        
        # Check if file exists and compare hash
        should_download = True
        if output_path.exists():
            current_hash = calculate_file_hash(output_path)
            if filename in existing_hashes and existing_hashes[filename] == current_hash:
                print(f"⏭️  Skipping {description} (already downloaded, hash matches)")
                current_hashes[filename] = current_hash
                should_download = False
                files_skipped += 1
            else:
                print(f"🔄 File exists but hash differs for {description}, re-downloading...")
        
        if should_download:
            if download_file(url, output_path, description):
                # For Parcels.zip we may apply fallback afterwards; hash only if accepted primary
                if filename != 'Parcels.zip':
                    file_hash = calculate_file_hash(output_path)
                    current_hashes[filename] = file_hash
                files_downloaded += 1
            else:
                print(f"⚠️  Failed to download {filename}")
    
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
    
    print(f"\n📊 Download Summary:")
    print(f"  Files downloaded: {files_downloaded}")
    print(f"  Files skipped (up to date): {files_skipped}")
    print(f"  Total primary files (excluding potential backup): {len(files_to_download)}")
    
    if files_downloaded > 0:
        print(f"\n✅ Download complete! Files saved to: {DOWNLOADS_DIR}")
        print("   Next step: Run step2_extract.py to extract the data")
    else:
        print(f"\n✅ All files up to date! No downloads needed.")
        print("   You can proceed with step2_extract.py if extraction is needed")

if __name__ == "__main__":
    main()
