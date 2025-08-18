# Harris County Property Lookup Tool

## Project Overview

A Flask-based web application that allows users to search Harris County property records by account number, street name, zip code, or owner name. The application downloads data from Harris County Appraisal District (HCAD), processes it through a 3‑step automated setup, and provides an interface with bedroom/bathroom counts, amenities, and comparable properties.

## Features Implemented ✅

### ✅ 1. Automated 3-Step Setup System

- **Master Script**: `setup_complete.py` – One-command setup
- **Step 1**: `step1_download.py` – Downloads ZIP files from HCAD
- **Step 2**: `step2_extract.py` – Extracts and processes text files
- **Step 3**: `step3_import.py` – Imports data to SQLite with amenities processing
- **Smart Hash Detection**: Skips unnecessary work if data unchanged
- **Complete Setup**: ~45 minutes first run, ~30 seconds subsequent runs

### ✅ 2. Enhanced Property Data

- **1,598,550** total properties loaded
- **287,507** properties with amenities (pools, garages, decks, etc.)
- **3,797** properties with bedroom/bathroom counts
- **Property ratings** and quality assessments
- **Address sorting** for organized search results

### ✅ 3. Comprehensive Search Features

- Search by account number, street name, zip code, or owner name
- **Bedroom/bathroom filtering** (where data available)
- **Amenities display** (pools, garages, fire features, etc.)
- **Property ratings** and quality scores
- **Address-sorted results** for easy browsing
- **Comparable properties** with distance-based matching

### ✅ 4. Modern Flask Web Application

- Clean, responsive Bootstrap 5 interface
- Form validation requiring at least one search criterion
- Flash messaging for user feedback
- Export to Excel/CSV functionality
- Automatic file cleanup for privacy

## Quick Start (Recommended)

```bash
# 1. Clone and setup environment
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest
python -m venv .venv
.venv\Scripts\activate  # Windows (source .venv/bin/activate on Linux/Mac)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Complete automated setup (one command!)
python setup_complete.py

# 4. Run the Flask application (choose one)
python -m taxprotest.app         # Module entry
# or after editable install: pip install -e .
taxprotest-app                   # Console script
# or (legacy fallback still present)
python app.py
# App runs at: http://127.0.0.1:5000
```bash

## Setup System Details

### Option 1: Complete Automated Setup

```bash
python setup_complete.py
```

Runs all 3 steps in sequence with progress reporting and error handling.

### Option 2: Individual Steps (Advanced)

```bash
# Step 1: Download data from HCAD (downloads ~500MB)
python step1_download.py

# Step 2: Extract and process files (~15 minutes)
python step2_extract.py

# Step 3: Import to SQLite with amenities (~30 minutes)
python step3_import.py
```

### Hash-Based Efficiency

The system tracks SHA256 hashes of downloaded and processed files:

- **First run**: Downloads, extracts, and imports everything (~45 minutes)
- **Subsequent runs**: Skips unchanged data (~30 seconds)
- **Selective updates**: Only processes changed components

## Enhanced Search Features ✨

| Feature | Description | Data Coverage |
|---------|-------------|---------------|
| **Address Search** | Partial/exact matching, alphabetically sorted | 1.6M properties |
| **Account Search** | Partial account number matching | All properties |
| **Owner Search** | Case-insensitive partial match | All properties |
| **Bedroom/Bath** | Room counts where available | 3,797 properties |
| **Amenities** | Pools, garages, decks, patios, fire features | 287,507 properties |
| **Property Ratings** | Overall and quality ratings | Where available |
| **Comparables** | Distance & size filtered matching | With coordinates |

## Project Structure (Refactored src/ layout)

```
TaxProtest/
├── pyproject.toml              # Packaging config (console script: taxprotest-app)
├── requirements.txt            # Base runtime dependencies
├── setup_complete.py           # Master setup script (runs all 3 steps)
├── step1_download.py           # Step 1: Download ZIP files from HCAD
├── step2_extract.py            # Step 2: Extract and process text files
├── step3_import.py             # Step 3: Import to SQLite with amenities
├── extract_data.py             # Search + legacy data utilities
├── src/
│   └── taxprotest/
│       ├── app/                # Flask application (factory + routes)
│       │   ├── __init__.py     # create_app()
│       │   ├── __main__.py     # python -m taxprotest.app entry
│       │   └── routes.py       # Blueprint routes
│       ├── comparables/        # Comparables engine components
│       │   ├── engine.py       # Progressive relaxation + caching
│       │   ├── scoring.py      # Penalty-based similarity scoring
│       │   ├── stats.py        # Pricing statistics & band counts
│       │   ├── export.py       # CSV/XLSX export (pandas optional)
│       │   └── config.py       # Band / weight configuration
│       └── config/             # Application configuration
│           └── settings.py     # Pydantic Settings (env prefix TAXPROTEST_)
├── templates/                  # Jinja templates (index, comparables, base)
├── static/                     # Static assets
├── data/                       # SQLite database & hash tracking
├── Exports/                    # Generated export artifacts
├── downloads/                  # Raw downloaded ZIP archives
├── text_files/                 # Extracted raw TXT/TSV data
└── docs/                       # Documentation PDFs / guides
```

Key refactor highlights:

- Modern src/ packaging with a single `taxprotest` namespace.
- Application factory pattern (`create_app`) enabling WSGI/ASGI deployment.
- Centralized configuration via Pydantic settings (environment overrides).
- Comparables engine separated from web layer, with scoring + pricing stats.
- Enhanced export supporting CSV and optional XLSX.

## Data Sources

The application downloads and processes these files from Harris County Appraisal District:

| File | Purpose | Records |
|------|---------|---------|
| `Real_acct.zip` | Property account records | 1.6M properties |
| `Building_res.zip` | Residential building details | 1.3M buildings |
| `Real_acct_owner.zip` | Property ownership information | 1.9M owner records |
| `extras_*.zip` | Additional features/fixtures | 8M+ records |
| `PP_files.zip` | Personal property records | Supplemental |
| `GIS_Public.zip` | Geographic coordinates | For comparables |

## Environment Setup

### 1. Clone and Navigate to Project

```bash
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Complete Setup

```bash
python setup_complete.py
```

### 5. Start Application

```bash
python app.py
# Access at: http://127.0.0.1:5000
```

## Search Tips & Usage

### Basic Searches

- **Street Name**: Enter "WALL ST" or "COMMERCE" for partial matching
- **Account Number**: Enter first 5–6 digits to find nearby properties
- **Zip Code**: Use "77040" to browse specific areas
- **Owner Name**: Search by last name or company name

### Advanced Features

- **Bedroom/Bathroom Data**: Available for ~3,800 properties
- **Amenities**: Pool, garage, deck, patio, fire features for ~287,000 properties
- **Property Ratings**: Quality and overall scores where available
- **Comparable Properties**: Distance and size-based matching

### Export Options

| Type | How | Requirements |
|------|-----|--------------|
| CSV  | Default | None |
| XLSX | /comparables/`<acct>`/export?fmt=xlsx | pandas + openpyxl (or xlsxwriter) |

Search export limit: 5,000 records. Comparables count controlled via `?max=` param.

## Technical Details

### Performance Optimizations

- **Hash-based change detection**: Skip unchanged data processing
- **Chunked database inserts**: 10,000 records per batch
- **Indexed searches**: Fast lookups on account, address, zip
- **Memory management**: Efficient processing of large datasets

### Database Schema

- **real_acct**: Core property records (account, address, values)
- **building_res**: Building details (year built, square footage)
- **property_derived**: Enhanced data (bedrooms, bathrooms, amenities, ratings)
- **owners**: Property ownership information
- **fixtures**: Detailed room and feature counts
- **extra_features**: Additional property amenities

### Data Processing Pipeline

1. **Download**: Retrieve ZIP files from HCAD (step1_download.py)
2. **Extract**: Process ZIP files to TSV format (step2_extract.py)
3. **Import**: Load into SQLite with amenities processing (step3_import.py)
4. **Serve**: Flask app provides search interface (app.py)

## Troubleshooting

### Common Issues

**Setup fails with download errors:**

```bash
# Check internet connection and retry
python step1_download.py
```

**Database seems incomplete:**

```bash
rm data/*_hashes.json
python setup_complete.py
```

**Search returns no amenities:**

- Normal – only ~18% of properties have amenities data
- Try searching "COMMERCE ST" or downtown areas for higher coverage

**Excel export not working:**

```bash
pip install pandas openpyxl
```

### Performance Notes

- **First setup**: ~45 minutes (downloads 500MB, processes 1.5GB)
- **Subsequent runs**: ~30 seconds (hash verification)
- **Database size**: 2.2GB final database
- **Memory usage**: ~200MB during normal operation

## System Requirements

- **Python**: 3.13+ (works on 3.12+)
- **Disk Space**: 4GB minimum (downloads + database + temp files)
- **Memory**: 2GB RAM recommended for large imports
- **Internet**: Required for initial data download

## Optional Enhancements

### Excel / XLSX Export Support

```bash
pip install pandas openpyxl
# Access XLSX via: /comparables/<acct>/export?fmt=xlsx
```

### Geographic Comparables

```bash
pip install geopandas shapely pyproj
```

## Environment Variables (Optional)

Namespaced via env prefix `TAXPROTEST_`:

```bash
set TAXPROTEST_SECRET_KEY=your-secret-key-here         # Windows
set TAXPROTEST_DATABASE_PATH=E:\data\database.sqlite  # Optional override
```

## Deployment Notes

### Local Development

- Default Flask development server (app.py)
- Runs on <http://127.0.0.1:5000>
- Auto-reload enabled for development

### Production Deployment

- Use a production WSGI server (waitress on Windows, gunicorn/uvicorn workers on Linux)
- Run via `taxprotest-app` or `python -m taxprotest.app`
- Set `TAXPROTEST_SECRET_KEY` and optionally `TAXPROTEST_DATABASE_PATH`
- Reverse proxy static assets & enable compression
- Schedule weekly data refresh (`setup_complete.py`)
- Add monitoring / health endpoint (future enhancement)

### Data Refresh Schedule

```bash
python setup_complete.py
```

## License & Data Usage

Data originates from Harris County Appraisal District public records. This tool is for educational and research purposes. Review HCAD usage policies before any commercial redistribution.

## Support & Contributing

Personal project for property research. Feel free to fork and adapt.

The application is fully functional and ready for property searches! 🏠

