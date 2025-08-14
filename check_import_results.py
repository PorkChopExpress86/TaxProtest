import sqlite3

conn = sqlite3.connect('data/database.sqlite')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables in database:')
for table in tables:
    print(f'  {table[0]}')
    
# Check fixtures table specifically
try:
    cursor.execute('SELECT COUNT(*) FROM fixtures')
    count = cursor.fetchone()[0]
    print(f'\nFixtures table has {count:,} rows')
    
    # Check sample data
    cursor.execute('SELECT acct, l_dscr FROM fixtures LIMIT 5')
    samples = cursor.fetchall()
    print('\nSample fixtures data:')
    for acct, desc in samples:
        print(f'  {acct}: {desc}')
        
except sqlite3.OperationalError as e:
    print(f'\nFixtures table error: {e}')

# Check property_derived for bedroom/bathroom data
cursor.execute('SELECT COUNT(*) FROM property_derived WHERE bedrooms IS NOT NULL OR bathrooms IS NOT NULL')
bed_bath_count = cursor.fetchone()[0]
print(f'\nProperties with bed/bath data: {bed_bath_count:,}')

# Check amenities
cursor.execute('SELECT COUNT(*) FROM property_derived WHERE amenities IS NOT NULL')
amenities_count = cursor.fetchone()[0]
print(f'Properties with amenities: {amenities_count:,}')

conn.close()
