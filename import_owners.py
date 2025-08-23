#!/usr/bin/env python3
"""
Import owners.txt to PostgreSQL with proper encoding handling
"""

import pandas as pd
from pathlib import Path
from db import get_connection
import sys

def import_owners():
    print('Direct PostgreSQL import for owners.txt...')
    
    text_dir = Path('/app/text_files')
    csv_path = text_dir / 'owners.txt'
    
    if not csv_path.exists():
        print('❌ owners.txt not found')
        return
    
    print(f'Processing {csv_path}...')
    
    # Read with pandas to clean data
    try:
        df = pd.read_csv(
            csv_path, 
            sep='\t', 
            encoding='latin-1', 
            dtype=str,
            on_bad_lines='skip',
            engine='python'
        )
    except Exception as e:
        print(f'❌ Error reading file: {e}')
        return
    
    print(f'  ✅ Read {len(df):,} rows with columns: {list(df.columns)}')
    
    # Clean column names
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Get connection and create table
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Drop table if exists
        cursor.execute('DROP TABLE IF EXISTS owners CASCADE')
        
        # Create table based on columns
        columns_sql = ', '.join([f'"{col}" TEXT' for col in df.columns])
        create_sql = f'CREATE TABLE owners ({columns_sql})'
        
        print(f'  Creating table with columns: {list(df.columns)}')
        cursor.execute(create_sql)
        
        # Insert data in batches
        batch_size = 10000
        total_inserted = 0
        
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            
            # Convert to list of tuples
            data = [tuple(row) for row in batch_df.values]
            
            # Insert batch
            placeholders = ','.join(['%s'] * len(df.columns))
            insert_sql = f'INSERT INTO owners VALUES ({placeholders})'
            
            cursor.executemany(insert_sql, data)
            total_inserted += len(data)
            
            if i % 50000 == 0:
                print(f'    Inserted {total_inserted:,} rows...')
        
        # Commit and verify
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM owners')
        count = cursor.fetchone()[0]
        print(f'  ✅ Successfully imported {count:,} rows to owners table')
        
        # Sample a few rows
        cursor.execute('SELECT * FROM owners LIMIT 3')
        sample = cursor.fetchall()
        print(f'  Sample data: {sample[0] if sample else "No data"}')
        
    except Exception as e:
        print(f'❌ Database error: {e}')
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    import_owners()
