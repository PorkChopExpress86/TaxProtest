#!/usr/bin/env python3
"""
Add estimated bedroom/bathroom counts and common amenities based on property data
"""
import sqlite3
import math

def add_estimated_residential_features():
    """Add estimated bedroom/bathroom counts based on square footage and property type"""
    
    conn = sqlite3.connect('database.sqlite')
    cursor = conn.cursor()
    
    # Add new columns for estimated features
    try:
        cursor.execute('ALTER TABLE building_res ADD COLUMN est_bedrooms INTEGER')
        cursor.execute('ALTER TABLE building_res ADD COLUMN est_bathrooms REAL')
        cursor.execute('ALTER TABLE building_res ADD COLUMN est_amenities TEXT')
        cursor.execute('ALTER TABLE building_res ADD COLUMN property_features TEXT')
        print("Added new columns for estimated residential features")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Columns already exist, updating existing data...")
        else:
            raise e
    
    # Update estimates based on building square footage and type
    cursor.execute("""
    UPDATE building_res 
    SET 
        est_bedrooms = CASE 
            -- Single family homes (1001)
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 800 THEN 1
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 1200 THEN 2
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 1800 THEN 3
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 2500 THEN 4
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) > 2500 THEN 5
            
            -- Duplexes (1002) - typically smaller per unit
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) <= 1200 THEN 2
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) <= 2000 THEN 3
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) > 2000 THEN 4
            
            -- Default for other property types
            ELSE CASE 
                WHEN CAST(im_sq_ft AS INTEGER) <= 600 THEN 1
                WHEN CAST(im_sq_ft AS INTEGER) <= 1000 THEN 2
                WHEN CAST(im_sq_ft AS INTEGER) <= 1600 THEN 3
                WHEN CAST(im_sq_ft AS INTEGER) <= 2400 THEN 4
                ELSE 5
            END
        END,
        
        est_bathrooms = CASE 
            -- Single family homes
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 800 THEN 1.0
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 1200 THEN 1.5
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 1800 THEN 2.0
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 2500 THEN 2.5
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) <= 3500 THEN 3.0
            WHEN impr_tp = '1001' AND CAST(im_sq_ft AS INTEGER) > 3500 THEN 3.5
            
            -- Duplexes
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) <= 1200 THEN 1.5
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) <= 2000 THEN 2.0
            WHEN impr_tp = '1002' AND CAST(im_sq_ft AS INTEGER) > 2000 THEN 2.5
            
            -- Default
            ELSE CASE 
                WHEN CAST(im_sq_ft AS INTEGER) <= 600 THEN 1.0
                WHEN CAST(im_sq_ft AS INTEGER) <= 1000 THEN 1.5
                WHEN CAST(im_sq_ft AS INTEGER) <= 1600 THEN 2.0
                WHEN CAST(im_sq_ft AS INTEGER) <= 2400 THEN 2.5
                ELSE 3.0
            END
        END
        
    WHERE im_sq_ft IS NOT NULL 
      AND im_sq_ft != '' 
      AND CAST(im_sq_ft AS INTEGER) > 0
    """)
    
    # Add amenity estimates based on property value, size, and quality
    cursor.execute("""
    UPDATE building_res 
    SET est_amenities = 
        CASE 
            -- High-end properties (good quality + large size)
            WHEN qa_cd IN ('A', 'B') AND CAST(im_sq_ft AS INTEGER) > 2500 THEN 
                'Pool, Fireplace, 2-Car Garage, Central AC/Heat, Security System'
            
            -- Mid-range properties 
            WHEN qa_cd IN ('B', 'C') AND CAST(im_sq_ft AS INTEGER) > 1500 THEN 
                'Fireplace, 1-Car Garage, Central AC/Heat'
                
            -- Basic properties
            WHEN qa_cd IN ('C', 'D') AND CAST(im_sq_ft AS INTEGER) > 1000 THEN 
                'Central AC/Heat, Parking'
                
            -- Older/smaller properties
            ELSE 'Basic HVAC'
        END,
        
    property_features = 
        CASE impr_tp 
            WHEN '1001' THEN 'Single Family Home'
            WHEN '1002' THEN 'Duplex'
            WHEN '1003' THEN 'Triplex'
            WHEN '1004' THEN 'Quadruplex'
            ELSE 'Residential Building'
        END || 
        CASE qa_cd 
            WHEN 'A' THEN ' - Excellent Condition'
            WHEN 'B' THEN ' - Good Condition' 
            WHEN 'C' THEN ' - Average Condition'
            WHEN 'D' THEN ' - Below Average Condition'
            WHEN 'E' THEN ' - Poor Condition'
            WHEN 'F' THEN ' - Very Poor Condition'
            ELSE ''
        END
        
    WHERE im_sq_ft IS NOT NULL 
      AND im_sq_ft != '' 
      AND CAST(im_sq_ft AS INTEGER) > 0
    """)
    
    rows_updated = cursor.rowcount
    conn.commit()
    
    print(f"Updated {rows_updated} records with estimated residential features")
    
    # Show sample of updated data
    cursor.execute("""
    SELECT acct, im_sq_ft, est_bedrooms, est_bathrooms, est_amenities, property_features
    FROM building_res 
    WHERE est_bedrooms IS NOT NULL 
    LIMIT 5
    """)
    
    print("\nSample of estimated features:")
    print("-" * 80)
    for row in cursor.fetchall():
        print(f"Account: {row[0]}")
        print(f"  Sq Ft: {row[1]}")
        print(f"  Est. Bedrooms: {row[2]}")
        print(f"  Est. Bathrooms: {row[3]}")
        print(f"  Est. Amenities: {row[4]}")
        print(f"  Property Type: {row[5]}")
        print()
    
    conn.close()

if __name__ == "__main__":
    add_estimated_residential_features()
