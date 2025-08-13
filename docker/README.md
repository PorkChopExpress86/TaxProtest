# 🐳 Docker Utilities

This directory contains Docker-specific scripts and utilities for containerized deployment.

## Files Overview

- **`docker_init.py`** - Container initialization and data setup
- **`docker_run.py`** - Container startup and Flask application runner
- **`quickstart.ps1`** - Windows PowerShell quick start script
- **`quickstart.sh`** - Linux/Mac quick start script

## Usage

### Direct Script Execution
```bash
# Initialize container data
python docker/docker_init.py

# Start Flask application in container
python docker/docker_run.py
```

### Quick Start Scripts
```bash
# Windows
.\docker\quickstart.ps1

# Linux/Mac  
./docker/quickstart.sh
```

These scripts provide interactive menus for Docker deployment tasks.
