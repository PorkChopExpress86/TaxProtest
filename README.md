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
- Generates CSV files with property search results
- Includes: Address, Zip Code, Build Year, Land/Building Values, Market Value, etc.
- Calculates price per square foot automatically
- Results limited to 5,000 records for performance

### ✅ 5. Automatic File Cleanup
- Downloaded CSV files are automatically deleted after 60 seconds
- Background thread handles cleanup without blocking user experience
- Privacy-focused approach

## Quick Start

### Option 1: Docker (Recommended)
```bash
# Clone and switch to Docker branch
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest
git checkout docker-containerization

# Quick start with interactive menu
./docker-quickstart.sh          # Linux/Mac
# or
.\docker-quickstart.ps1         # Windows PowerShell

# Manual Docker commands
docker-compose --profile init up data-init    # Initialize data (first time)
docker-compose up -d                          # Start application
# Access at: http://localhost:5000
```

### Option 2: Native Installation
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

## Docker Deployment

For containerized deployment, see [DOCKER.md](DOCKER.md) for complete instructions.

### Quick Docker Start
```bash
# Initialize data (first time only)
docker-compose --profile init up data-init

# Start application
docker-compose up -d

# Start with database browser
docker-compose --profile tools up -d
```

## New Features ✨

### ✅ Exact Match Search
- **Checkbox Option**: Users can now choose between partial and exact street name matching
- **Precise Results**: Exact match returns only properties with the complete address
- **Flexible Search**: Partial match continues to work for broader searches

### ✅ CSV Export Formatting
- **Professional Output**: Price per square foot now formatted to exactly 2 decimal places
- **Consistent Data**: All currency values maintain proper formatting standards
- **Excel Compatible**: CSV files open cleanly in Excel with proper number formatting

## File Structure
```
TaxProtest/
├── app.py                 # Main Flask application
├── download_extract.py    # Data download and extraction
├── extract_data.py        # SQLite database loader
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template with Bootstrap 5
│   └── index.html        # Search form interface
├── static/
│   └── style.css         # Custom styling
├── data/                 # SQLite database files
│   └── database.sqlite   # Main property database
├── downloads/            # Downloaded ZIP files storage
├── extracted/            # Extracted data files
├── Exports/              # Generated CSV files (auto-cleanup)
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
- Python 3.13.6 with virtual environment
- Flask + Flask-WTF for web framework and forms
- SQLite for database (no external dependencies)
- Bootstrap 5 for responsive UI

The application is fully functional and ready for property searches! 🏠
