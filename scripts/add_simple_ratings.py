#!/usr/bin/env python3
"""
Add optimized property rating system to the database
"""

import sqlite3

def add_simple_rating_system():
    """Add a simplified but effective property rating system"""
    conn = sqlite3.connect('database.sqlite')
    cursor = conn.cursor()
    
    print("Adding simplified property ratings...")
    
    # Calculate ratings based on available quality indicators
    cursor.execute("""
    UPDATE building_res 
    SET 
        overall_rating = CASE 
            WHEN qa_cd = 'A' THEN 8.5
            WHEN qa_cd = 'B' THEN 7.0
            WHEN qa_cd = 'C' THEN 5.5
            WHEN qa_cd = 'D' THEN 4.0
            WHEN qa_cd = 'E' THEN 2.5
            ELSE 5.0
        END +
        CASE 
            WHEN CAST(date_erected AS INTEGER) >= 2020 THEN 1.0
            WHEN CAST(date_erected AS INTEGER) >= 2010 THEN 0.5
            WHEN CAST(date_erected AS INTEGER) >= 2000 THEN 0.0
            WHEN CAST(date_erected AS INTEGER) >= 1990 THEN -0.3
            WHEN CAST(date_erected AS INTEGER) < 1990 THEN -0.5
            ELSE 0.0
        END +
        CASE 
            WHEN est_bedrooms >= 4 AND est_bathrooms >= 3 THEN 0.5
            WHEN est_bedrooms >= 3 AND est_bathrooms >= 2 THEN 0.2
            ELSE 0.0
        END +
        CASE 
            WHEN est_amenities LIKE '%Premium%' THEN 0.3
            WHEN est_amenities LIKE '%Modern%' OR est_amenities LIKE '%Updated%' THEN 0.1
            ELSE 0.0
        END,
        
        quality_rating = CASE 
            WHEN qa_cd = 'A' THEN 9.0
            WHEN qa_cd = 'B' THEN 7.5
            WHEN qa_cd = 'C' THEN 6.0
            WHEN qa_cd = 'D' THEN 4.0
            WHEN qa_cd = 'E' THEN 2.0
            ELSE 5.0
        END,
        
        value_rating = CASE 
            WHEN qa_cd IN ('A', 'B') AND CAST(date_erected AS INTEGER) >= 2010 THEN 8.0
            WHEN qa_cd IN ('A', 'B') THEN 7.0
            WHEN qa_cd = 'C' AND CAST(date_erected AS INTEGER) >= 2010 THEN 6.5
            WHEN qa_cd = 'C' THEN 5.5
            WHEN qa_cd IN ('D', 'E') AND CAST(date_erected AS INTEGER) >= 2010 THEN 5.0
            ELSE 4.0
        END,
        
        rating_explanation = 
        CASE qa_cd
            WHEN 'A' THEN 'Excellent quality construction'
            WHEN 'B' THEN 'Good quality construction'
            WHEN 'C' THEN 'Average quality construction'
            WHEN 'D' THEN 'Below average construction'
            WHEN 'E' THEN 'Basic construction'
            ELSE 'Standard construction'
        END ||
        CASE 
            WHEN CAST(date_erected AS INTEGER) >= 2020 THEN '; Recently built'
            WHEN CAST(date_erected AS INTEGER) >= 2010 THEN '; Modern construction'
            WHEN CAST(date_erected AS INTEGER) < 1990 THEN '; Mature property'
            ELSE ''
        END ||
        CASE 
            WHEN est_bedrooms >= 4 THEN '; Spacious layout'
            WHEN est_bedrooms <= 2 THEN '; Compact layout'
            ELSE ''
        END ||
        CASE 
            WHEN est_amenities LIKE '%Premium%' THEN '; Premium features'
            WHEN est_amenities LIKE '%Modern%' THEN '; Modern amenities'
            ELSE ''
        END
    WHERE qa_cd IS NOT NULL OR date_erected IS NOT NULL
    """)
    
    # Ensure ratings stay within 1-10 range
    cursor.execute("""
    UPDATE building_res 
    SET overall_rating = CASE 
        WHEN overall_rating > 10 THEN 10.0
        WHEN overall_rating < 1 THEN 1.0
        ELSE overall_rating
    END
    WHERE overall_rating IS NOT NULL
    """)
    
    conn.commit()
    
    # Show results
    cursor.execute("SELECT COUNT(*) FROM building_res WHERE overall_rating IS NOT NULL")
    count = cursor.fetchone()[0]
    print(f"Updated {count:,} properties with ratings")
    
    # Show rating distribution
    cursor.execute("""
    SELECT 
        CAST(overall_rating AS INTEGER) as rating_floor,
        COUNT(*) as count,
        AVG(overall_rating) as avg_rating
    FROM building_res 
    WHERE overall_rating IS NOT NULL 
    GROUP BY CAST(overall_rating AS INTEGER) 
    ORDER BY rating_floor
    """)
    
    print("\nRating Distribution:")
    total_rated = 0
    for rating, count, avg in cursor.fetchall():
        stars = "★" * rating
        print(f"  {rating}-{rating+1} stars: {count:7,} properties (avg: {avg:.1f}) {stars}")
        total_rated += count
    
    print(f"\nTotal rated properties: {total_rated:,}")
    
    # Show sample high-rated properties
    print("\n=== Sample Highly Rated Properties ===")
    cursor.execute("""
    SELECT b.acct, b.overall_rating, b.quality_rating, b.rating_explanation,
           r.tot_mkt_val, r.str_num, r.str_pfx_dir, r.str_name, r.mail_zip
    FROM building_res b
    JOIN real_acct r ON b.acct = r.acct
    WHERE b.overall_rating >= 8.0
    ORDER BY b.overall_rating DESC
    LIMIT 5
    """)
    
    for row in cursor.fetchall():
        acct, rating, quality, explanation, value, num, pfx, name, zip_code = row
        address = f"{num or ''} {pfx or ''} {name or ''}".strip()
        print(f"Rating: {rating:.1f} | ${int(float(value or 0)):,} | {address}, {zip_code}")
        print(f"  {explanation}")
        print()
    
    conn.close()

if __name__ == '__main__':
    add_simple_rating_system()
