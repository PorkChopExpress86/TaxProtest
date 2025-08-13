import sqlite3

conn = sqlite3.connect('database.sqlite')
cursor = conn.cursor()

# Get table names
tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

# Get counts
for table in tables:
    count = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table} count: {count:,}')

# Sample a few records from real_acct
print("\nSample real_acct records:")
sample = cursor.execute("SELECT * FROM real_acct LIMIT 3").fetchall()
for row in sample:
    print(row[:5])  # First 5 columns

conn.close()
