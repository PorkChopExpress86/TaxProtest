# Harris County Property Lookup Tool

[![CI](https://github.com/PorkChopExpress86/TaxProtest/actions/workflows/ci.yml/badge.svg)](https://github.com/PorkChopExpress86/TaxProtest/actions/workflows/ci.yml)

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

## Quick Start (Container-First Recommended) 🐳

```powershell
# 1. Clone
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest

# 2. Build images (app + dependencies)
docker compose build

# 3. Start Postgres + app (app served at http://localhost:5001)
docker compose up -d postgres
docker compose up -d taxprotest

# 4. (Optional) Run one‑shot Postgres ingestion (text + geo) with profiling
docker compose run --rm ingest

# 5. Development server with live reload (http://localhost:5002)
docker compose up -d taxprotest-dev

# 6. Run tests inside container
docker compose run --rm taxprotest pytest -q
```

Local virtual environments are no longer required when using Docker; all
dependencies (including psycopg + optional geo stack) install inside the image.
Use a venv only if you intentionally run the pipeline directly on the host.

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

## Project Structure

```
TaxProtest/
├── src/taxprotest/
│   ├── app/            # Flask app package (factory + routes)
│   ├── comparables/    # Comparables engine (engine, scoring, stats, export, config)
│   ├── config/         # Settings / configuration
│   ├── logging_config/ # Logging setup utilities
│   ├── wsgi.py         # Gunicorn entrypoint
│   └── __init__.py
├── scripts/            # Operational helpers (ingest_postgres, init script, refresh helpers)
├── extract_data.py     # Data loading + search utilities
├── load_geo_data.py    # Geo ingestion (Postgres + PostGIS)
├── setup_complete.py   # Orchestrates steps 1–3
├── step1_download.py   # Legacy step script
├── step2_extract.py    # Legacy step script
├── step3_import.py     # Legacy step script
├── templates/          # Jinja templates
├── static/             # Static assets
├── tests/              # Unit & integration tests
├── downloads/          # Raw ZIP downloads
├── text_files/         # Extracted intermediate text
├── data/               # SQLite DB + hash tracking
├── Exports/            # Generated export artifacts
├── docs/               # Supplemental documentation
├── Makefile            # Common developer commands
├── CONTRIBUTING.md     # Contribution guidelines
├── docker-compose.yml  # Multi-service orchestration
└── Dockerfile          # Container build
```

Housekeeping: removed obsolete duplicate root `comparables/` package and skipped duplicate `test_scoring.py`; canonical code lives under `src/taxprotest/`.

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

```bash
git clone https://github.com/PorkChopExpress86/TaxProtest.git
```

## Environment Setup (Alternative Local / Non-Docker)

If you prefer running directly on the host (not required):

```powershell
python -m venv .venv; . .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_complete.py
python app.py  # http://127.0.0.1:5000
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
set TAXPROTEST_DATABASE_URL=postgresql://user:pass@localhost:5432/taxprotest  # Use Postgres (optional)
```

docker run -e POSTGRES_USER=tax -e POSTGRES_PASSWORD=tax -e POSTGRES_DB=taxprotest -p 5434:5432 -v pg_data:/var/lib/postgresql/data postgres:16-alpine
docker compose up -d --build
\n### Container-Native Postgres (Default Path)

`docker-compose.yml` now provisions:

| Service | Purpose |
|---------|---------|
| postgres | PostgreSQL 16 + persistent volume |
| taxprotest | Production Gunicorn app (port 5001) |
| taxprotest-dev | Dev server with live reload (port 5002) |
| ingest | One-shot data + geo loader into Postgres |

Full ingestion inside containers (copies + PostGIS geom):

```powershell
docker compose up -d postgres
docker compose run --rm ingest
docker compose up -d taxprotest
```

Re-run ingestion after updates:

```powershell
docker compose run --rm ingest
```

`ingest` performs: init script (extensions/indexes) → COPY text tables → geo ingest with PostGIS geometry + GIST index.

### Phase 2 (Current)

Recent performance upgrades when Postgres is enabled:

- COPY fast path now applied to: `property_geo`, `real_acct`, `building_res`, `owners`, and supplemental tables (`fixtures`, `extra_features`, `building_other`, `structural_elem1`, `structural_elem2`).
- Fallback path automatically switches to buffered or batched inserts if streaming COPY is unavailable.
- New optional profiling output gated by environment flag `TAXPROTEST_PROFILE_LOAD=1` prints per‑stage timings (e.g. `core real_acct`, `owners COPY`, `supp fixtures COPY`).
- Extended indexes added in `scripts/init_postgres.sql` for owners & supplemental tables to improve downstream joins.

How to enable profiling (PowerShell example):

```powershell
$env:TAXPROTEST_PROFILE_LOAD="1"; python setup_complete.py
```

Sample output line:

```text
⏱️  core real_acct 12.34s
```

If you re-run frequently and want to ensure indexes after data refresh:

```powershell
python scripts/run_init_postgres.py
```

You can safely run the init script multiple times; it only creates missing indexes.

Planned next (optional): defer index creation until after COPY for marginal extra speed; PostGIS geometry column for spatial queries.

Rollback: unset `TAXPROTEST_DATABASE_URL` to fall back to embedded SQLite file.

### (Optional) PostGIS Spatial Enablement

If you're using PostgreSQL and want spatial indexes:

1. Ensure Postgres superuser or extension privileges.
2. Run:

```powershell
python scripts\run_init_postgres.py
```

What happens:

- Enables `postgis` extension (idempotent)
- Adds `geom` geometry(Point,4326) to `property_geo`
- Backfills from numeric longitude/latitude
- Creates GIST index `idx_property_geo_geom`

Sample distance query (5 mile radius):

```sql
SELECT ra.acct, ra.site_addr_1, pd.overall_rating
FROM real_acct ra
JOIN property_geo pg ON pg.acct = ra.acct
LEFT JOIN property_derived pd ON pd.acct = ra.acct
WHERE pg.geom IS NOT NULL
  AND ST_DWithin(pg.geom, ST_SetSRID(ST_MakePoint(-95.370,29.760),4326), 1609.34 * 5)
LIMIT 25;
```

Planned integration: use ST_DWithin for comparables when PostGIS present; fallback to Python haversine otherwise.

## Development Workflow & Tooling

### Pre-commit Hooks

This repo includes a `.pre-commit-config.yaml` with:

- Ruff (lint + format)
- Black (idempotent formatting safety net)
- Mypy (type checking)
- Basic hygiene hooks (trailing whitespace, large file guard)

Enable locally (recommended):

```powershell
pip install pre-commit  # or pip install .[dev]
pre-commit install
```

Run on all files manually:

```powershell
pre-commit run --all-files
```

### CI Matrix (SQLite + Postgres)

GitHub Actions runs tests against:

- SQLite (default embedded path)
- Postgres + PostGIS (service container)

Ingestion timings (with `TAXPROTEST_PROFILE_LOAD=1`) are uploaded as build artifacts for the Postgres job.

### Failing Type Checks

`mypy` now fails the CI build on errors (was previously soft). Fix locally before pushing or rely on pre-commit to catch issues.

### Profiling Data Loads

To profile COPY / ingestion locally inside the container dev service:

```powershell
$env:TAXPROTEST_PROFILE_LOAD="1"; docker compose run --rm ingest
```

Artifacts will show per-stage timing in CI; locally you see them in stdout.

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

### Automated Monthly Refresh (15th of Each Month)

You can automate the refresh using the new orchestrator script `refresh.py` which performs a smart incremental run (download -> extract -> import) and exits with codes:

| Exit Code | Meaning |
|-----------|---------|
| 0 | Nothing changed |
| 10 | Downloads updated only |
| 20 | Extraction ran (archives changed) |
| 30 | Import ran (database updated) |

#### Option A: Windows Task Scheduler

1. Open Task Scheduler → Create Task.
2. Triggers → New → Monthly → select Day 15 → OK.
3. Action → Start a Program.
4. Program/script:
`powershell`
5. Arguments (adjust paths as needed):
`-NoProfile -ExecutionPolicy Bypass -Command "cd 'E:\TaxProtest'; & 'E:\Python313\python.exe' refresh.py | Tee-Object -FilePath 'E:\TaxProtest\logs\refresh_$(Get-Date -Format yyyyMMdd_HHmmss).log'"`
6. Conditions: Uncheck "Start the task only if the computer is on AC power" if on a desktop.
7. Settings: Enable "Run task as soon as possible after a scheduled start is missed".

Log files will appear under `logs/` (create the folder if missing). The JSON status is always written to `data/last_refresh_report.json`.

#### Option B: Docker Compose (Manual / External Scheduler)

If using Docker Compose, trigger a refresh container run (ensure volumes persist):

PowerShell example:

```powershell
docker compose run --rm refresh
```

(Name aligns with the `refresh` service in `docker-compose.yml`). Schedule this command with Task Scheduler the same way—set Program/script to `docker` and Arguments to `compose run --rm refresh`.

#### Option C: Cron (Linux)

Add to crontab (`crontab -e`):

```cron
0 3 15 * * /usr/bin/python3 /opt/TaxProtest/refresh.py >> /opt/TaxProtest/logs/refresh_$(date +\%Y\%m\%d).log 2>&1
```

#### Forcing a Full Rebuild

To force extraction/import even if hashes match:

```bash
python step3_import.py --force
```

Or delete the hash files in `data/` before running `refresh.py`.

#### Programmatic Consumption

After a scheduled run, parse `data/last_refresh_report.json` to determine if downstream tasks (e.g., analytics exports) should run.

## License & Data Usage

Data originates from Harris County Appraisal District public records. This tool is for educational and research purposes. Review HCAD usage policies before any commercial redistribution.

## Support & Contributing

Personal project for property research. Feel free to fork and adapt.

The application is fully functional and ready for property searches! 🏠

