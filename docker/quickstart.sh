#!/bin/bash
# Quick start script for Docker deployment

set -e

echo "🐳 Harris County Property Lookup - Docker Quick Start"
echo "===================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your settings before running in production"
fi

# Function to show menu
show_menu() {
    echo ""
    echo "Choose an option:"
    echo "1) Initialize data (required for first run - ~10 minutes)"
    echo "2) Start application"
    echo "3) Start application + database browser"
    echo "4) View application logs"
    echo "5) Stop all services"
    echo "6) Clean up (remove containers and data)"
    echo "7) Exit"
    echo ""
}

# Function to initialize data
init_data() {
    echo "🚀 Initializing Harris County property data..."
    echo "This will download and process ~2GB of data (takes ~10 minutes)"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose --profile init up data-init
        echo "✅ Data initialization complete!"
    else
        echo "❌ Data initialization cancelled"
    fi
}

# Function to start application
start_app() {
    # Check if database exists
    if [ ! -f "./data/database.sqlite" ]; then
        echo "❌ Database not found! Please initialize data first (option 1)"
        return 1
    fi
    
    echo "🚀 Starting Harris County Property Lookup application..."
    docker-compose up -d property-lookup
    echo "✅ Application started!"
    echo "🌐 Access at: http://localhost:5000"
}

# Function to start with tools
start_with_tools() {
    if [ ! -f "./data/database.sqlite" ]; then
        echo "❌ Database not found! Please initialize data first (option 1)"
        return 1
    fi
    
    echo "🚀 Starting application with database browser..."
    docker-compose --profile tools up -d
    echo "✅ Services started!"
    echo "🌐 Application: http://localhost:5000"
    echo "🗄️  Database Browser: http://localhost:8080"
}

# Function to show logs
show_logs() {
    echo "📋 Application logs (press Ctrl+C to exit):"
    docker-compose logs -f property-lookup
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping all services..."
    docker-compose down
    echo "✅ All services stopped"
}

# Function to clean up
cleanup() {
    echo "🧹 This will remove all containers, images, and data"
    read -p "Are you sure? This cannot be undone! (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down --volumes --remove-orphans
        docker rmi harris-property-lookup 2>/dev/null || true
        rm -rf data downloads extracted text_files logs Exports
        echo "✅ Cleanup complete"
    else
        echo "❌ Cleanup cancelled"
    fi
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice (1-7): " choice
    
    case $choice in
        1)
            init_data
            ;;
        2)
            start_app
            ;;
        3)
            start_with_tools
            ;;
        4)
            show_logs
            ;;
        5)
            stop_services
            ;;
        6)
            cleanup
            ;;
        7)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid option. Please choose 1-7."
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done
