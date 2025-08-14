import sqlite3
import os
from datetime import datetime

# Quick test of the updated extraction logic
conn = sqlite3.connect('data/database.sqlite')
cursor = conn.cursor()

print("Testing updated extraction logic...")

# Test amenities loading
amenities_data = {}
try:
    cursor.execute("SELECT acct, l_dscr FROM extra_features WHERE l_dscr IS NOT NULL LIMIT 1000")
    print("Loading amenities data...")
    for acct, desc in cursor.fetchall():
        desc = desc.strip() if desc else ""
        if desc and any(keyword in desc.upper() for keyword in ['POOL', 'GARAGE', 'DECK', 'PATIO', 'FIRE', 'SPA']):
            acct_trimmed = acct.strip()
            if acct_trimmed not in amenities_data:
                amenities_data[acct_trimmed] = []
            amenities_data[acct_trimmed].append(desc)
    print(f"Loaded amenities for {len(amenities_data)} properties (sample)")
except Exception as e:
    print(f"Error loading amenities: {e}")

# Test fixture loading
fixture_counts = {}
try:
    cursor.execute("SELECT acct, type, type_dscr, units FROM fixtures WHERE type IS NOT NULL AND units IS NOT NULL LIMIT 1000")
    for acct, ftype, type_desc, units in cursor.fetchall():
        acct_trimmed = acct.strip()
        if acct_trimmed not in fixture_counts:
            fixture_counts[acct_trimmed] = {'bedrooms': 0, 'bathrooms': 0.0}
        
        try:
            unit_count = float(units) if units else 0
        except:
            unit_count = 0
        
        ftype = ftype.strip().upper() if ftype else ''
        desc = (type_desc or '').upper()
        
        if ftype == 'RMB' or 'BEDROOM' in desc:
            fixture_counts[acct_trimmed]['bedrooms'] += int(unit_count)
        elif ftype == 'RMF' or 'FULL BATH' in desc:
            fixture_counts[acct_trimmed]['bathrooms'] += unit_count
        elif ftype == 'RMH' or 'HALF BATH' in desc:
            fixture_counts[acct_trimmed]['bathrooms'] += unit_count * 0.5
            
    print(f"Loaded bed/bath data for {len(fixture_counts)} properties (sample)")
except Exception as e:
    print(f"Error loading fixtures: {e}")

# Test account format matching
cursor.execute("SELECT acct FROM building_res LIMIT 5")
building_accounts = [row[0] for row in cursor.fetchall()]
print(f"\nBuilding account samples (padded): {[repr(acc) for acc in building_accounts[:3]]}")

cursor.execute("SELECT acct FROM fixtures LIMIT 5")
fixture_accounts = [row[0] for row in cursor.fetchall()]
print(f"Fixture account samples (unpadded): {[repr(acc) for acc in fixture_accounts[:3]]}")

# Test matching logic
test_account = building_accounts[0].strip()
print(f"\nTest account (trimmed): {repr(test_account)}")
print(f"Has bed/bath data: {test_account in fixture_counts}")
print(f"Has amenities data: {test_account in amenities_data}")

if test_account in fixture_counts:
    print(f"Bed/bath: {fixture_counts[test_account]}")
if test_account in amenities_data:
    print(f"Amenities: {amenities_data[test_account]}")

conn.close()
print("Test completed!")
