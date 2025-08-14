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
from pathlib import Path

# Setup paths
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DOWNLOADS_DIR = BASE_DIR / "downloads"
EXTRACTED_DIR = BASE_DIR / "extracted"
TEXT_FILES_DIR = BASE_DIR / "text_files"
HASH_FILE = BASE_DIR / "data" / "extraction_hashes.json"

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
    
    try:
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
        print(f"    ❌ Error: {zip_path.name} is not a valid ZIP file")
        return []
    except Exception as e:
        print(f"    ❌ Error extracting {zip_path.name}: {e}")
        return []
    
    return extracted_files

def main():
    print("📦 Harris County Tax Data Extractor")
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
            "target_files": None,  # Extract all
            "description": "GIS Data"
        }
    }
    
    # Load existing extraction hashes  
    existing_hashes = load_existing_hashes()
    current_hashes = {}
    files_extracted = 0
    files_skipped = 0
    
    for zip_filename, rules in extraction_rules.items():
        zip_path = DOWNLOADS_DIR / zip_filename
        
        if not zip_path.exists():
            print(f"⚠️  {zip_filename} not found in downloads directory")
            continue
            
        # Calculate current ZIP hash
        zip_hash = calculate_file_hash(zip_path)
        
        # Check if we need to extract
        should_extract = True
        if zip_filename in existing_hashes and existing_hashes[zip_filename] == zip_hash:
            print(f"⏭️  Skipping {rules['description']} (already extracted, hash matches)")
            current_hashes[zip_filename] = zip_hash
            should_extract = False
            files_skipped += 1
        else:
            if zip_filename in existing_hashes:
                print(f"🔄 ZIP file changed for {rules['description']}, re-extracting...")
            else:
                print(f"📦 Extracting {rules['description']}...")
        
        if should_extract:
            # Determine extraction destination
            if zip_filename == "GIS_Public.zip":
                extract_to = EXTRACTED_DIR
            else:
                extract_to = TEXT_FILES_DIR
                
            # Extract files
            extracted_files = extract_zip_file(zip_path, extract_to, rules['target_files'])
            
            if extracted_files:
                print(f"    ✅ Extracted {len(extracted_files)} files")
                current_hashes[zip_filename] = zip_hash
                files_extracted += 1
            else:
                print(f"    ❌ No files extracted from {zip_filename}")
    
    # Save updated hashes
    save_hashes(current_hashes)
    
    print(f"\n📊 Extraction Summary:")
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
    
    print(f"\n📄 Key Files Status:")
    for file_path in key_files:
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {file_path.name} ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {file_path.name} (missing)")
    
    if files_extracted > 0:
        print(f"\n✅ Extraction complete!")
        print("   Next step: Run step3_import.py to import data into SQLite")
    else:
        print(f"\n✅ All files up to date! No extraction needed.")
        print("   You can proceed with step3_import.py if database import is needed")

if __name__ == "__main__":
    main()
