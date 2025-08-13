#!/usr/bin/env python3
"""
Simple test script to verify Docker container setup
"""
import sys
from pathlib import Path

def test_docker_environment():
    """Test the Docker environment setup"""
    print("🧪 Testing Docker Environment")
    print("=" * 30)
    
    # Test 1: Python version
    print(f"✅ Python version: {sys.version}")
    
    # Test 2: Required directories
    required_dirs = ['/app/data', '/app/Exports', '/app/logs', '/app/templates']
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ Directory exists: {dir_path}")
        else:
            print(f"❌ Directory missing: {dir_path}")
    
    # Test 3: Flask import
    try:
        from flask import Flask
        print("✅ Flask import successful")
    except ImportError as e:
        print(f"❌ Flask import failed: {e}")
        return False
    
    # Test 4: App files
    app_files = ['/app/app.py', '/app/docker_run.py', '/app/extract_data.py']
    for file_path in app_files:
        if Path(file_path).exists():
            print(f"✅ File exists: {file_path}")
        else:
            print(f"❌ File missing: {file_path}")
    
    # Test 5: Environment variables
    import os
    env_vars = ['PYTHONPATH', 'FLASK_APP']
    for var in env_vars:
        value = os.environ.get(var, 'Not set')
        print(f"ℹ️  {var}: {value}")
    
    print("\n🐳 Docker environment test complete!")
    return True

if __name__ == "__main__":
    success = test_docker_environment()
    sys.exit(0 if success else 1)
