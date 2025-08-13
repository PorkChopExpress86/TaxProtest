# 🔧 Data Processing Scripts

This directory contains scripts for downloading, processing, and enhancing Harris County property data.

## Scripts Overview

### Core Processing
- **`download_extract.py`** - Downloads Harris County data files from HCAD
- **`extract_data.py`** - Processes data into SQLite database  
- **`update.py`** - Updates existing database with new data

### Enhancement Scripts  
- **`add_residential_estimates.py`** - Adds estimated property features
- **`add_simple_ratings.py`** - Adds property rating system

## Usage

```bash
# Standard workflow
python scripts/download_extract.py    # Download data
python scripts/extract_data.py        # Create database
python scripts/add_residential_estimates.py  # Add estimates (optional)
python scripts/add_simple_ratings.py  # Add ratings (optional)
```

## Docker Usage

These scripts are automatically executed during Docker initialization:
```bash
docker-compose --profile init up data-init
```
