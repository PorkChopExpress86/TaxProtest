#!/usr/bin/env python3
"""
Import real_acct.txt to PostgreSQL with proper encoding handling
"""

import pandas as pd
from pathlib import Path
from db import get_connection
import sys

def import_real_acct():
    print('Direct PostgreSQL import for real_acct.txt...')
    
    text_dir = Path('/app/text_files')
    csv_path = text_dir / 'real_acct.txt'
    
    if not csv_path.exists():
        print('❌ real_acct.txt not found')
        return
    
    print(f'Processing {csv_path}...')
    
    # Read with pandas to clean data
    try:
        # Try different encodings for real_acct which is larger
        for encoding in ['latin-1', 'cp1252', 'utf-8']:
            try:
                print(f'  Trying encoding: {encoding}')
                # First try just reading headers
                df_test = pd.read_csv(csv_path, sep='\t', encoding=encoding, nrows=1)
                print(f'  ✅ Headers work with {encoding}: {len(df_test.columns)} columns')
                
                # Now try full read with error handling
                df = pd.read_csv(
                    csv_path, 
                    sep='\t', 
                    encoding=encoding, 
                    dtype=str,
                    on_bad_lines='skip',
                    engine='python'
                )
                print(f'  ✅ Full read successful with {encoding}')
                break
            except Exception as e:
                print(f'  ❌ Encoding {encoding} failed: {e}')
                continue
        else:
            print('❌ Could not read file with any encoding')
            return
            
    except Exception as e:
        print(f'❌ Error reading file: {e}')
        return
    
    print(f'  ✅ Read {len(df):,} rows with columns: {list(df.columns)[:5]}...')
    
    # Clean column names
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Get connection and create table
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Drop table if exists
        cursor.execute('DROP TABLE IF EXISTS real_acct CASCADE')
        
        # Create table based on columns
        columns_sql = ', '.join([f'"{col}" TEXT' for col in df.columns])
        create_sql = f'CREATE TABLE real_acct ({columns_sql})'
        
        print(f'  Creating table with {len(df.columns)} columns')
        cursor.execute(create_sql)
        
        # Insert data in batches
        batch_size = 5000  # Smaller batches for large table
        total_inserted = 0
        
        print(f'  Starting batch insert of {len(df):,} rows...')
        
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            
            # Convert to list of tuples
            data = [tuple(row) for row in batch_df.values]
            
            # Insert batch
            placeholders = ','.join(['%s'] * len(df.columns))
            insert_sql = f'INSERT INTO real_acct VALUES ({placeholders})'
            
            cursor.executemany(insert_sql, data)
            total_inserted += len(data)
            
            if i % 25000 == 0:
                print(f'    Inserted {total_inserted:,} rows...')
        
        # Commit and verify
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM real_acct')
        count = cursor.fetchone()[0]
        print(f'  ✅ Successfully imported {count:,} rows to real_acct table')
        
        # Sample a few rows
        cursor.execute('SELECT acct, situs_addr FROM real_acct LIMIT 3')
        sample = cursor.fetchall()
        print(f'  Sample data: {sample[0] if sample else "No data"}')
        
    except Exception as e:
        print(f'❌ Database error: {e}')
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    import_real_acct()
