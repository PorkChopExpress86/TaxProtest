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
from pathlib import Path

def run_step(script_name, description):
    """Run a setup step and return success status"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Script {script_name} not found")
        return False

def main():
    print("🏠 Harris County Tax Data - Complete Setup")
    print("🔄 This will download, extract, and import all tax data")
    print("⚡ Steps are skipped automatically if data is up-to-date")
    
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
        if run_step(script, description):
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
