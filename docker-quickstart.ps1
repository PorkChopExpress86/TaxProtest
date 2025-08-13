# Harris County Property Lookup - Docker Quick Start (PowerShell)
# Usage: .\docker-quickstart.ps1

param(
    [string]$Action = "menu"
)

function Write-Header {
    Write-Host "🐳 Harris County Property Lookup - Docker Quick Start" -ForegroundColor Cyan
    Write-Host "====================================================" -ForegroundColor Cyan
}

function Test-DockerRunning {
    try {
        docker info | Out-Null
        Write-Host "✅ Docker is running" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
        return $false
    }
}

function Initialize-Environment {
    if (-not (Test-Path ".env")) {
        Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "⚠️  Please edit .env file with your settings before running in production" -ForegroundColor Yellow
    }
}

function Show-Menu {
    Write-Host ""
    Write-Host "Choose an option:" -ForegroundColor White
    Write-Host "1) Initialize data (required for first run - ~10 minutes)" -ForegroundColor Cyan
    Write-Host "2) Start application" -ForegroundColor Cyan
    Write-Host "3) Start application + database browser" -ForegroundColor Cyan
    Write-Host "4) View application logs" -ForegroundColor Cyan
    Write-Host "5) Stop all services" -ForegroundColor Cyan
    Write-Host "6) Clean up (remove containers and data)" -ForegroundColor Cyan
    Write-Host "7) Exit" -ForegroundColor Cyan
    Write-Host ""
}

function Initialize-Data {
    Write-Host "🚀 Initializing Harris County property data..." -ForegroundColor Yellow
    Write-Host "This will download and process ~2GB of data (takes ~10 minutes)" -ForegroundColor Yellow
    $confirm = Read-Host "Continue? (y/N)"
    
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        docker-compose --profile init up data-init
        Write-Host "✅ Data initialization complete!" -ForegroundColor Green
    }
    else {
        Write-Host "❌ Data initialization cancelled" -ForegroundColor Red
    }
}

function Start-Application {
    if (-not (Test-Path ".\data\database.sqlite")) {
        Write-Host "❌ Database not found! Please initialize data first (option 1)" -ForegroundColor Red
        return
    }
    
    Write-Host "🚀 Starting Harris County Property Lookup application..." -ForegroundColor Yellow
    docker-compose up -d property-lookup
    Write-Host "✅ Application started!" -ForegroundColor Green
    Write-Host "🌐 Access at: http://localhost:5000" -ForegroundColor Cyan
}

function Start-WithTools {
    if (-not (Test-Path ".\data\database.sqlite")) {
        Write-Host "❌ Database not found! Please initialize data first (option 1)" -ForegroundColor Red
        return
    }
    
    Write-Host "🚀 Starting application with database browser..." -ForegroundColor Yellow
    docker-compose --profile tools up -d
    Write-Host "✅ Services started!" -ForegroundColor Green
    Write-Host "🌐 Application: http://localhost:5000" -ForegroundColor Cyan
    Write-Host "🗄️  Database Browser: http://localhost:8080" -ForegroundColor Cyan
}

function Show-Logs {
    Write-Host "📋 Application logs (press Ctrl+C to exit):" -ForegroundColor Yellow
    docker-compose logs -f property-lookup
}

function Stop-Services {
    Write-Host "🛑 Stopping all services..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "✅ All services stopped" -ForegroundColor Green
}

function Remove-Everything {
    Write-Host "🧹 This will remove all containers, images, and data" -ForegroundColor Red
    $confirm = Read-Host "Are you sure? This cannot be undone! (y/N)"
    
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        docker-compose down --volumes --remove-orphans
        docker rmi harris-property-lookup 2>$null
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue data, downloads, extracted, text_files, logs, Exports
        Write-Host "✅ Cleanup complete" -ForegroundColor Green
    }
    else {
        Write-Host "❌ Cleanup cancelled" -ForegroundColor Red
    }
}

# Main execution
Write-Header

if (-not (Test-DockerRunning)) {
    exit 1
}

Initialize-Environment

# Handle command line arguments
switch ($Action) {
    "init" { Initialize-Data; exit 0 }
    "start" { Start-Application; exit 0 }
    "tools" { Start-WithTools; exit 0 }
    "logs" { Show-Logs; exit 0 }
    "stop" { Stop-Services; exit 0 }
    "clean" { Remove-Everything; exit 0 }
}

# Interactive menu
while ($true) {
    Show-Menu
    $choice = Read-Host "Enter your choice (1-7)"
    
    switch ($choice) {
        "1" { Initialize-Data }
        "2" { Start-Application }
        "3" { Start-WithTools }
        "4" { Show-Logs }
        "5" { Stop-Services }
        "6" { Remove-Everything }
        "7" { 
            Write-Host "👋 Goodbye!" -ForegroundColor Green
            exit 0 
        }
        default { 
            Write-Host "❌ Invalid option. Please choose 1-7." -ForegroundColor Red 
        }
    }
    
    Write-Host ""
    Read-Host "Press Enter to continue..."
}
