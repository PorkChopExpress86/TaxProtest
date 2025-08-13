# Project Requirements: TaxProtest Property Lookup Tool

## Overview
A Flask-based web application for property lookup, data import, and Excel export, using a SQLite backend and data from official property database exports.

## Functional Requirements
1. Download property database export files from the official source (URL or FTP).
2. Extract/unzip the downloaded files.
3. Load the extracted data into a SQLite database, using the provided codebook for schema.
4. Provide a web interface to:
   - Search by name or address
   - Display results in a table
   - Export results to Excel and download
   - Automatically delete the Excel file after download

## Technical Requirements
- Python (Flask, pandas, openpyxl, requests)
- SQLite for data storage
- User-friendly and secure web interface
- Scripts/instructions for each step (download, extract, load, run)

## Documentation
- Maintain step-by-step instructions in `docs/`.
- Update this file as requirements evolve.
