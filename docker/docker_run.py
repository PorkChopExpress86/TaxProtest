#!/usr/bin/env python3
"""
Docker-optimized startup script for the Flask Property Lookup Tool
"""
import os
import sys
import time
from pathlib import Path

def check_docker_environment():
    """Check if the Docker environment is properly set up"""
    
    print("🐳 Harris County Property Lookup Tool (Docker)")
    print("=" * 50)
    
    # Check if database exists
    db_path = Path('/app/data/database.sqlite')
    if not db_path.exists():
        print("❌ Database not found!")
        print("Run data initialization first:")
        print("  docker-compose --profile init up data-init")
        return False
    
    # Check database size
    db_size = db_path.stat().st_size / (1024 * 1024)  # MB
    print(f"✅ Database found: {db_size:.1f} MB")
    
    # Check required directories
    required_dirs = ['/app/data', '/app/Exports', '/app/logs']
    for dir_path in required_dirs:
        Path(dir_path).mkdir(exist_ok=True)
    
    print("✅ Directory structure verified")
    
    # Check environment variables
    secret_key = os.environ.get('SECRET_KEY', 'dev-key')
    if secret_key == 'dev-key' or 'dev' in secret_key.lower():
        print("⚠️  Using development secret key")
        print("   Set SECRET_KEY environment variable for production")
    else:
        print("✅ Production secret key configured")
    
    return True

def wait_for_dependencies():
    """Wait for any dependencies to be ready"""
    # Add health checks here if needed
    time.sleep(2)  # Brief pause for container startup

def main():
    """Main Docker startup function"""
    
    if not check_docker_environment():
        sys.exit(1)
    
    wait_for_dependencies()
    
    # Import and configure the Flask app
    try:
        from app.app import app
        
        # Docker-specific configuration
        app.config.update(
            HOST=os.environ.get('HOST', '0.0.0.0'),
            PORT=int(os.environ.get('PORT', 5000)),
            DEBUG=os.environ.get('DEBUG', 'false').lower() == 'true'
        )
        
        print("✅ Flask application configured for Docker")
        print(f"🌐 Starting server on {app.config['HOST']}:{app.config['PORT']}")
        print("🔧 Debug mode:", "enabled" if app.config['DEBUG'] else "disabled")
        print("\n🐳 Container ready for connections")
        print("📋 Access the application at: http://localhost:5000")
        print("🛠️  Database browser at: http://localhost:8080 (if enabled)")
        print("\nPress Ctrl+C to stop the container\n")
        
        # Run the Flask application
        app.run(
            host=app.config['HOST'],
            port=app.config['PORT'],
            debug=app.config['DEBUG']
        )
        
    except ImportError as e:
        print(f"❌ Error importing Flask app: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
