#!/usr/bin/env python3
"""
Production-ready startup script for the Flask Property Lookup Tool
"""
import os
import sys
from pathlib import Path

def check_environment():
    """Check if the environment is properly set up"""
    
    # Check if database exists
    db_path = Path('data/database.sqlite')
    if not db_path.exists():
        print("❌ Database not found!")
        print("Please run the following commands first:")
        print("  python download_extract.py")
        print("  python extract_data.py")
        return False
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Virtual environment not detected")
        print("Recommended: Activate virtual environment first")
        print("  .venv\\Scripts\\activate  # Windows")
        print("  source .venv/bin/activate  # Linux/Mac")
    
    return True

def main():
    """Main startup function"""
    print("🏠 Harris County Property Lookup Tool")
    print("=" * 40)
    
    if not check_environment():
        sys.exit(1)
    
    # Set production environment if not set
    if not os.environ.get('SECRET_KEY'):
        print("ℹ️  Using development secret key")
        print("   For production, set SECRET_KEY environment variable")
    
    # Import and run the Flask app
    try:
        from app import app
        print("✅ Starting Flask application...")
        print("🌐 Access the application at: http://127.0.0.1:5000")
        print("🔧 Debug mode enabled for development")
        print("\nPress Ctrl+C to stop the server\n")
        
        app.run(host="0.0.0.0", port=5000, debug=True)
        
    except ImportError as e:
        print(f"❌ Error importing Flask app: {e}")
        print("Please check that all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
