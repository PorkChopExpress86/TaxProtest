#!/usr/bin/env python3
"""
Add comprehensive property rating system to the database
"""

import sqlite3
import math
from pathlib import Path

def calculate_property_rating(building_data, market_data, neighborhood_stats):
    """
    Calculate comprehensive property rating (1-10 scale)
    
    Factors considered:
    1. Construction Quality (qa_cd, eff)
    2. Age and Condition (date_erected, recent improvements)
    3. Value Performance (price per sq ft vs neighborhood)
    4. Property Size and Features (bedrooms, bathrooms, amenities)
    5. Market Position (value vs neighborhood average)
    """
    
    rating = 5.0  # Start with average rating
    
    # 1. CONSTRUCTION QUALITY (up to +/- 2 points)
    qa_cd = building_data.get('qa_cd', '').strip()
    eff = building_data.get('eff', 0)
    
    if qa_cd == 'A':
        rating += 2.0  # Excellent quality
    elif qa_cd == 'B':
        rating += 1.0  # Good quality
    elif qa_cd == 'C':
        rating += 0.0  # Average quality
    elif qa_cd == 'D':
        rating -= 1.0  # Below average
    elif qa_cd == 'E':
        rating -= 2.0  # Poor quality
    
    # Efficiency factor (higher is better)
    try:
        eff_num = float(eff) if eff else 200
        if eff_num >= 210:
            rating += 0.5  # Very efficient design
        elif eff_num >= 205:
            rating += 0.25  # Good efficiency
        elif eff_num < 190:
            rating -= 0.5  # Poor efficiency
    except:
        pass
    
    # 2. AGE AND CONDITION (up to +/- 1.5 points)
    try:
        date_erected = building_data.get('date_erected', '')
        if date_erected and date_erected.isdigit():
            year_built = int(date_erected)
            age = 2025 - year_built
            
            if age <= 5:
                rating += 1.5  # Very new
            elif age <= 15:
                rating += 1.0  # Relatively new
            elif age <= 30:
                rating += 0.0  # Average age
            elif age <= 50:
                rating -= 0.5  # Older
            else:
                rating -= 1.0  # Very old
    except:
        pass
    
    # 3. VALUE PERFORMANCE (up to +/- 1.5 points)
    price_per_sqft = market_data.get('price_per_sqft', 0)
    neighborhood_avg = neighborhood_stats.get('avg_price_per_sqft', 0)
    
    if price_per_sqft > 0 and neighborhood_avg > 0:
        value_ratio = price_per_sqft / neighborhood_avg
        if value_ratio >= 1.3:
            rating += 1.5  # Premium property
        elif value_ratio >= 1.1:
            rating += 0.75  # Above average value
        elif value_ratio >= 0.9:
            rating += 0.0  # Average value
        elif value_ratio >= 0.7:
            rating -= 0.5  # Below average value
        else:
            rating -= 1.0  # Significantly undervalued
    
    # 4. PROPERTY FEATURES (up to +/- 1 point)
    bedrooms = building_data.get('est_bedrooms', 0)
    bathrooms = building_data.get('est_bathrooms', 0)
    amenities = building_data.get('est_amenities', '')
    
    feature_score = 0
    if bedrooms >= 4:
        feature_score += 0.3
    elif bedrooms >= 3:
        feature_score += 0.1
    
    if bathrooms >= 3:
        feature_score += 0.3
    elif bathrooms >= 2:
        feature_score += 0.1
    
    if amenities and 'Premium' in amenities:
        feature_score += 0.4
    elif amenities and ('Modern' in amenities or 'Updated' in amenities):
        feature_score += 0.2
    
    rating += feature_score
    
    # 5. MARKET POSITION (up to +/- 0.5 points)
    tot_mkt_val = market_data.get('tot_mkt_val', 0)
    neighborhood_med = neighborhood_stats.get('median_value', 0)
    
    if tot_mkt_val > 0 and neighborhood_med > 0:
        market_ratio = tot_mkt_val / neighborhood_med
        if market_ratio >= 1.5:
            rating += 0.5  # High-end property
        elif market_ratio <= 0.6:
            rating -= 0.3  # Lower-end property
    
    # Ensure rating stays within 1-10 range
    rating = max(1.0, min(10.0, rating))
    
    return round(rating, 1)

def calculate_neighborhood_stats(cursor, zip_code):
    """Calculate neighborhood statistics for comparison"""
    cursor.execute("""
    SELECT 
        AVG(CAST(r.tot_mkt_val AS REAL) / CAST(b.gross_ar AS REAL)) as avg_price_per_sqft,
        AVG(CAST(r.tot_mkt_val AS REAL)) as median_value,
        COUNT(*) as property_count
    FROM real_acct r
    JOIN building_res b ON r.acct = b.acct
    WHERE r.mail_zip = ? 
    AND CAST(r.tot_mkt_val AS REAL) > 50000 
    AND CAST(b.gross_ar AS REAL) > 500
    """, (zip_code,))
    
    result = cursor.fetchone()
    return {
        'avg_price_per_sqft': result[0] or 0,
        'median_value': result[1] or 0,
        'property_count': result[2] or 0
    }

def add_rating_system():
    """Add property rating columns and calculate ratings"""
    conn = sqlite3.connect('database.sqlite')
    cursor = conn.cursor()
    
    # Add new rating columns
    try:
        cursor.execute('ALTER TABLE building_res ADD COLUMN overall_rating REAL')
        cursor.execute('ALTER TABLE building_res ADD COLUMN quality_rating REAL')
        cursor.execute('ALTER TABLE building_res ADD COLUMN value_rating REAL')
        cursor.execute('ALTER TABLE building_res ADD COLUMN rating_explanation TEXT')
        print("Added rating columns to building_res table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Rating columns already exist")
        else:
            print(f"Error adding columns: {e}")
    
    # Get all properties with sufficient data
    cursor.execute("""
    SELECT 
        b.acct, b.qa_cd, b.eff, b.date_erected, b.est_bedrooms, 
        b.est_bathrooms, b.est_amenities, b.gross_ar,
        r.tot_mkt_val, r.bld_val, r.land_val, r.mail_zip
    FROM building_res b
    JOIN real_acct r ON b.acct = r.acct
    WHERE r.tot_mkt_val IS NOT NULL 
    AND r.tot_mkt_val != ''
    AND CAST(r.tot_mkt_val AS REAL) > 10000
    """)
    
    properties = cursor.fetchall()
    print(f"Processing {len(properties)} properties for rating calculation...")
    
    # Cache neighborhood stats by zip code
    neighborhood_cache = {}
    
    updated_count = 0
    for i, prop in enumerate(properties):
        if i % 10000 == 0:
            print(f"Processed {i}/{len(properties)} properties...")
        
        acct, qa_cd, eff, date_erected, bedrooms, bathrooms, amenities, gross_ar, tot_mkt_val, bld_val, land_val, mail_zip = prop
        
        # Get neighborhood stats (cached)
        if mail_zip not in neighborhood_cache:
            neighborhood_cache[mail_zip] = calculate_neighborhood_stats(cursor, mail_zip)
        neighborhood_stats = neighborhood_cache[mail_zip]
        
        # Prepare data for rating calculation
        building_data = {
            'qa_cd': qa_cd,
            'eff': eff,
            'date_erected': date_erected,
            'est_bedrooms': bedrooms,
            'est_bathrooms': bathrooms,
            'est_amenities': amenities
        }
        
        # Calculate price per sq ft
        price_per_sqft = 0
        try:
            if gross_ar and float(gross_ar) > 0:
                price_per_sqft = float(tot_mkt_val) / float(gross_ar)
        except:
            pass
        
        market_data = {
            'tot_mkt_val': float(tot_mkt_val) if tot_mkt_val else 0,
            'price_per_sqft': price_per_sqft
        }
        
        # Calculate overall rating
        overall_rating = calculate_property_rating(building_data, market_data, neighborhood_stats)
        
        # Calculate component ratings
        quality_rating = 5.0
        if qa_cd == 'A':
            quality_rating = 9.0
        elif qa_cd == 'B':
            quality_rating = 7.5
        elif qa_cd == 'C':
            quality_rating = 6.0
        elif qa_cd == 'D':
            quality_rating = 4.0
        elif qa_cd == 'E':
            quality_rating = 2.0
        
        # Value rating based on price per sq ft vs neighborhood
        value_rating = 5.0
        if price_per_sqft > 0 and neighborhood_stats['avg_price_per_sqft'] > 0:
            ratio = price_per_sqft / neighborhood_stats['avg_price_per_sqft']
            if ratio >= 1.3:
                value_rating = 8.5
            elif ratio >= 1.1:
                value_rating = 7.0
            elif ratio >= 0.9:
                value_rating = 5.5
            elif ratio >= 0.7:
                value_rating = 4.0
            else:
                value_rating = 2.5
        
        # Create explanation
        explanation_parts = []
        if qa_cd in ['A', 'B']:
            explanation_parts.append(f"High quality construction ({qa_cd})")
        elif qa_cd in ['D', 'E']:
            explanation_parts.append(f"Lower quality construction ({qa_cd})")
        
        try:
            age = 2025 - int(date_erected) if date_erected and date_erected.isdigit() else None
            if age and age <= 10:
                explanation_parts.append("Recently built")
            elif age and age >= 50:
                explanation_parts.append("Mature property")
        except:
            pass
        
        if price_per_sqft > 0 and neighborhood_stats['avg_price_per_sqft'] > 0:
            ratio = price_per_sqft / neighborhood_stats['avg_price_per_sqft']
            if ratio >= 1.2:
                explanation_parts.append("Premium neighborhood value")
            elif ratio <= 0.8:
                explanation_parts.append("Good value opportunity")
        
        explanation = "; ".join(explanation_parts) if explanation_parts else "Standard residential property"
        
        # Update database
        cursor.execute("""
        UPDATE building_res 
        SET overall_rating = ?, quality_rating = ?, value_rating = ?, rating_explanation = ?
        WHERE acct = ?
        """, (overall_rating, quality_rating, value_rating, explanation, acct))
        
        updated_count += 1
    
    conn.commit()
    print(f"\nRating calculation complete! Updated {updated_count} properties.")
    
    # Show rating distribution
    cursor.execute("SELECT overall_rating, COUNT(*) FROM building_res WHERE overall_rating IS NOT NULL GROUP BY CAST(overall_rating AS INTEGER) ORDER BY overall_rating")
    distribution = cursor.fetchall()
    print("\nRating Distribution:")
    for rating, count in distribution:
        stars = "★" * int(rating)
        print(f"  {rating:3.0f}+ stars: {count:6,} properties {stars}")
    
    conn.close()

if __name__ == '__main__':
    add_rating_system()
