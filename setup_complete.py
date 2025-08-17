"""
Harris County Tax Data - Complete Setup
======================================

This script runs the complete 3-step setup process:
1. Download ZIP files (with hash checking)
2. Extract files (with hash checking) 
3. Import into SQLite (with hash checking and amenities)

Each step is skipped if data hasn't changed (based on file hashes).
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path

def run_step(script_name, description, extra_args=None):
    """Run a setup step and return success status. extra_args is a list of additional
    command-line args to pass to the step script (e.g. ['--force'])."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")

    # Prefer the project's virtual environment Python if available so child
    # scripts run with the same virtualenv without needing to "activate" a shell.
    def find_venv_python():
        # 1) VIRTUAL_ENV (set when a venv is activated)
        venv_path = os.environ.get('VIRTUAL_ENV')
        if venv_path:
            p = Path(venv_path) / 'Scripts' / 'python.exe'
            if p.exists():
                return str(p)

        # 2) Common venv directory names in project root
        for name in ('.venv', 'venv', 'env', '.env'):
            p = Path(name) / 'Scripts' / 'python.exe'
            if p.exists():
                return str(p)

        # 3) Fallback to current interpreter
        return sys.executable

    python_exe = find_venv_python()
    if python_exe != sys.executable:
        print(f"Using virtualenv python: {python_exe}")

    cmd = [python_exe, script_name]
    if extra_args:
        cmd.extend(extra_args)

    try:
        result = subprocess.run(cmd, capture_output=False, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Script {script_name} not found")
        return False


def remove_file_if_exists(path: Path):
    try:
        if path.exists():
            path.unlink()
            print(f"  Removed: {path}")
            return True
    except Exception as e:
        print(f"  Could not remove {path}: {e}")
    return False

def main():
    parser = argparse.ArgumentParser(description="Run complete setup (download, extract, import).")
    parser.add_argument('--force', action='store_true', help='Force all steps (ignore hash checks)')
    parser.add_argument('--force-download', action='store_true', help='Force re-download (ignore download hashes)')
    parser.add_argument('--force-extract', action='store_true', help='Force re-extract (ignore extraction hashes)')
    parser.add_argument('--force-import', action='store_true', help='Force re-import (ignore import hashes)')
    # Aliases for convenience
    parser.add_argument('--redo', action='store_true', help='Alias for --force (redo all steps)')
    parser.add_argument('--redo-all', action='store_true', help='Alias for --force (redo all steps)')
    parser.add_argument('--redownload', action='store_true', help='Alias for --force-download (force re-download)')
    args = parser.parse_args()

    print("🏠 Harris County Tax Data - Complete Setup")
    print("🔄 This will download, extract, and import all tax data")
    print("⚡ Steps are skipped automatically if data is up-to-date")
    
    # If any force flag provided, remove the relevant hash files so steps won't skip
    data_dir = Path('data')
    download_hash = data_dir / 'download_hashes.json'
    extraction_hash = data_dir / 'extraction_hashes.json'
    import_hash = data_dir / 'import_hashes.json'

    # Treat alias flags as the corresponding force flags
    if args.force or args.force_download or args.redownload or args.redo or args.redo_all:
        print('\n⚡ Forcing download: removing download hashes (if present)')
        remove_file_if_exists(download_hash)

    if args.force or args.force_extract or args.redo or args.redo_all:
        print('\n⚡ Forcing extract: removing extraction hashes (if present)')
        remove_file_if_exists(extraction_hash)

    if args.force or args.force_import or args.redo or args.redo_all:
        print('\n⚡ Forcing import: removing import hashes (if present)')
        remove_file_if_exists(import_hash)

    # Check if setup scripts exist
    scripts = [
        ("step1_download.py", "Step 1: Download Data"),
        ("step2_extract.py", "Step 2: Extract Data"), 
        ("step3_import.py", "Step 3: Import to SQLite")
    ]
    
    missing_scripts = []
    for script, _ in scripts:
        if not Path(script).exists():
            missing_scripts.append(script)
    
    if missing_scripts:
        print(f"\n❌ Missing setup scripts:")
        for script in missing_scripts:
            print(f"   {script}")
        print("\n   Make sure all setup scripts are in the current directory.")
        return
    
    # Run each step
    success_count = 0
    total_steps = len(scripts)
    
    for script, description in scripts:
        # Build extra args to propagate forcing to child scripts (safe: child scripts ignore unknown args)
        extra_args = []
        # Global force or aliases
        if args.force or args.redo or args.redo_all:
            extra_args.append('--force')
        else:
            # Per-step forcing (including redownload alias)
            if script == 'step1_download.py' and (args.force_download or args.redownload):
                extra_args.append('--force')
            if script == 'step2_extract.py' and args.force_extract:
                extra_args.append('--force')
            if script == 'step3_import.py' and args.force_import:
                extra_args.append('--force')

        if run_step(script, description, extra_args):
            success_count += 1
            print(f"✅ {description} completed successfully")
        else:
            print(f"❌ {description} failed")
            print(f"\n🛑 Setup stopped at step {success_count + 1} of {total_steps}")
            print(f"   Fix the error above and run this script again")
            return
    
    # All steps completed
    print(f"\n{'='*60}")
    print(f"🎉 SETUP COMPLETE!")
    print(f"{'='*60}")
    print(f"✅ All {total_steps} steps completed successfully")
    print(f"")
    print(f"📊 Your Harris County tax database is ready!")
    print(f"")
    print(f"🚀 Next steps:")
    print(f"   1. Start the Flask app: python app.py")
    print(f"   2. Open browser to: http://127.0.0.1:5000")
    print(f"   3. Search properties by account, street, zip, or owner")
    print(f"")
    print(f"🔍 Features available:")
    print(f"   • Property search with filters")
    print(f"   • Bedroom/bathroom counts")
    print(f"   • Amenities (pools, garages, decks, etc.)")
    print(f"   • Property comparables with distance")
    print(f"   • Excel export functionality")

if __name__ == "__main__":
    main()
