#!/usr/bin/env python3
"""
Docker-specific data initialization script
Handles the complete data download and processing workflow for containers
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout.strip():
                print("Output:", result.stdout.strip())
            return True
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            if result.stderr.strip():
                print("Error:", result.stderr.strip())
            if result.stdout.strip():
                print("Output:", result.stdout.strip())
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {description} timed out after 1 hour")
        return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False

def check_prerequisites():
    """Check if required directories and files exist"""
    print("🔍 Checking prerequisites...")
    
    # Check if we're in the right directory
    if not Path('/app/download_extract.py').exists():
        print("❌ download_extract.py not found")
        return False
    
    if not Path('/app/extract_data.py').exists():
        print("❌ extract_data.py not found")
        return False
    
    # Create required directories
    dirs = ['/app/downloads', '/app/extracted', '/app/data', '/app/text_files', '/app/logs']
    for dir_path in dirs:
        Path(dir_path).mkdir(exist_ok=True)
        print(f"✅ Directory ready: {dir_path}")
    
    return True

def main():
    """Main initialization process"""
    print("🐳 Docker Data Initialization for Harris County Property Lookup")
    print("=" * 65)
    
    if not check_prerequisites():
        print("❌ Prerequisites check failed")
        sys.exit(1)
    
    # Step 1: Download data
    success = run_command(
        "python /app/download_extract.py",
        "Downloading Harris County data files"
    )
    
    if not success:
        print("⚠️  Download failed, but continuing with existing data if available...")
    
    # Step 2: Process data into SQLite
    success = run_command(
        "python /app/extract_data.py",
        "Processing data into SQLite database"
    )
    
    if not success:
        print("❌ Database creation failed")
        sys.exit(1)
    
    # Check if database was created
    db_path = Path('/app/data/database.sqlite')
    if db_path.exists():
        db_size = db_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ Database created: {db_size:.1f} MB")
    else:
        print("❌ Database file not found after processing")
        sys.exit(1)
    
    # Step 3: Add residential estimates (optional)
    success = run_command(
        "python /app/add_residential_estimates.py",
        "Adding residential feature estimates"
    )
    
    if not success:
        print("⚠️  Residential estimates failed, but continuing...")
    
    # Step 4: Add property ratings (optional)
    success = run_command(
        "python /app/add_simple_ratings.py",
        "Adding property rating system"
    )
    
    if not success:
        print("⚠️  Property ratings failed, but continuing...")
    
    # Final validation
    print("\n🎯 Final Validation")
    print("=" * 20)
    
    # Test database connectivity
    try:
        import sqlite3
        conn = sqlite3.connect('/app/data/database.sqlite')
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ Database tables: {', '.join(tables)}")
        
        # Check record counts
        for table in ['real_acct', 'building_res']:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ {table}: {count:,} records")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database validation failed: {e}")
        sys.exit(1)
    
    print("\n🎉 Data initialization completed successfully!")
    print("🚀 Ready to start the Flask application")

if __name__ == "__main__":
    main()
