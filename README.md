# Harris County Property Lookup Tool

## Project Overview
A Flask-based web application that allows users to search Harris County property records by account number, street name, or zip code. The application downloads data from Harris County Appraisal District (HCAD), loads it into a SQLite database, and provides a user-friendly interface to search and export property information.

## Features Implemented ✅

### ✅ 1. Data Download & Extraction
- **Script**: `download_extract.py`
- Downloads 7 ZIP files from HCAD including:
  - Real_building_land.zip
  - Real_acct_owner.zip  
  - Hearing_files.zip
  - Code_description_real.zip
  - PP_files.zip
  - Code_description_pp.zip
  - GIS_Public.zip
- Automatically creates directories and extracts relevant files
- SSL certificate verification enabled
- Error handling for download failures

### ✅ 2. Database Loading  
- **Script**: `extract_data.py`
- Loads extracted TSV files into SQLite database (`database.sqlite`)
- Handles large files efficiently with chunked inserts (10,000 rows per batch)
- Automatic encoding detection (mbcs/utf-8 fallback)
- Currently loaded: 1,299,809 building records + 1,598,550 account records

### ✅ 3. Flask Web Application
- **Main app**: `app.py`
- Clean, responsive Bootstrap 5 interface
- Search by account number, street name, and/or zip code
- Form validation requiring at least one search criteria
- Flash message system for user feedback

### ✅ 4. Export & Download
- Generates CSV files with property search results (default)
- Optional Excel (.xlsx) export when pandas + openpyxl installed
- Includes: Address, Zip Code, Build Year, Land/Building Values, Market Value, etc.
- Calculates price per square foot automatically
- Results limited to 5,000 records for performance

### ✅ 5. Automatic File Cleanup
- Downloaded CSV files are automatically deleted after 60 seconds
- Background thread handles cleanup without blocking user experience
- Privacy-focused approach

## Quick Start

```bash
# 1. Clone and setup environment
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest
python -m venv .venv
.venv\Scripts\activate  # Windows (.venv/bin/activate on Linux/Mac)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download and load data (takes ~10 minutes)
python download_extract.py
python extract_data.py

# 4. Run the Flask application
python app.py
# Access at: http://127.0.0.1:5000
```

## Key Search Features ✨

| Feature | Description |
|---------|-------------|
| Account Search | Partial account number matching |
| Street Search | Partial or exact match (toggle) |
| Owner Name Search | Case-insensitive partial match across owner name fields |
| Zip Filter | Narrow results by zip code |
| Price / Sq Ft | Calculated for each result when area present |
| Comparables | Distance & size filtered list (requires GIS + coordinates) |

## File Structure
```
TaxProtest/
├── app.py                 # Main Flask application
├── download_extract.py    # Data download and extraction
├── extract_data.py        # SQLite database loader
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html          # Base template with Bootstrap 5
│   ├── index.html         # Search form interface (now includes owner + comparables link)
│   └── comparables.html   # Comparable properties view
├── static/
│   └── style.css         # Custom styling
├── data/                 # SQLite database files
│   └── database.sqlite   # Main property database
├── downloads/            # Downloaded ZIP files storage
├── extracted/            # Extracted data files
├── Exports/              # Generated export files (auto-cleanup)
├── logs/                 # Application logs
├── text_files/           # Legacy: Extracted TSV data files  
├── zipped_data/          # Legacy: Downloaded ZIP files
└── docs/                 # Documentation and step-by-step guides
```

## Environment Setup

1. **Clone and Navigate to Project**:
   ```bash
   git clone https://github.com/PorkChopExpress86/TaxProtest.git
   cd TaxProtest
   ```

2. **Create Virtual Environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Environment Variables** (Optional, for production):
   ```bash
   set SECRET_KEY=your-secret-key-here  # Windows
   # export SECRET_KEY=your-secret-key-here  # Linux/Mac
   ```

## Search Tips
- **Account Number**: Enter first 5-6 digits to find nearby properties
- **Street Name**: Use partial names; combine with zip code for precision
- **Zip Code**: Use alone for area overview or combine with street name

## Technical Details
- **Database**: SQLite with 2.9M+ records total
- **Performance**: 5,000 record limit per search, chunked database inserts
- **Security**: HTTPS downloads, input validation, automatic file cleanup
- **Encoding**: Handles Windows-1252/MBCS and UTF-8 encodings automatically

## Environment
- Python 3.13+ (works on 3.12+)
- Flask + Flask-WTF UI
- SQLite (file-based, zero external server)
- Bootstrap 5 for responsive UI
- Optional: pandas + openpyxl (Excel export), geopandas stack (distance comparables)

The application is fully functional and ready for property searches! 🏠

## Optional: Excel Export
Install extras:
```
pip install pandas openpyxl
```
The Download button will then produce an .xlsx file; otherwise it falls back to a CSV.

## Optional: Distance-Based Comparables
To enable geographic filtering (distance / size):
```
pip install -r requirements-geo.txt
pip install pandas openpyxl   # if Excel export also desired
python scripts/process_gis_data.py
```
This builds a `property_geo` table derived from the GIS shapefile. Without it, the Comparables page may show no results.

## Minimal Production Notes
- Set `SECRET_KEY` environment variable.
- Run behind a production WSGI server (e.g. gunicorn) if deploying beyond local usage.
- Schedule periodic data refresh by re-running `download_extract.py` + `extract_data.py`.

## License / Data Source
Data originates from Harris County Appraisal District public data. Review their usage policies before redistribution.

