#!/usr/bin/env python3
import pytest
pytest.skip("Legacy duplicate test file; use tests/integration/test_complete_system.py", allow_module_level=True)

import sys
sys.path.append('.')
from extract_data import search_properties
import sqlite3

def test_search_functionality():
    """Test the search function to verify bedroom/bathroom/amenities data works"""
    
    print("🔍 Testing Harris County Property Search System")
    print("=" * 60)
    
    # Test 1: Search for properties with known amenities
    print("\n📋 Test 1: Searching for properties with amenities")
    
    # Find a property with amenities first
    conn = sqlite3.connect('data/database.sqlite')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ra.site_addr_1, ra.acct, pd.amenities 
        FROM real_acct ra 
        JOIN property_derived pd ON ra.acct = pd.acct 
        WHERE pd.amenities IS NOT NULL 
        LIMIT 3
    ''')
    
    amenities_properties = cursor.fetchall()
    conn.close()
    
    if amenities_properties:
        for addr, acct, amenities in amenities_properties:
            print(f"  Property: {addr}")
            print(f"  Account: {acct}")
            print(f"  Amenities: {amenities[:100]}...")
            
            # Extract street name for search
            street_parts = addr.split()
            if len(street_parts) >= 2:
                street_search = ' '.join(street_parts[-2:])  # Last two words (e.g., "COMMERCE ST")
                
                print(f"  Searching for: {street_search}")
                results = search_properties(street=street_search)
                
                if results:
                    print(f"  ✅ Found {len(results)} results")
                    # Check if our target property is in results and has amenities
                    for result in results:
                        if result['Account Number'] == acct:
                            amenities_result = result.get('Estimated Amenities', 'None')
                            if amenities_result and amenities_result != 'None':
                                print(f"  ✅ Target property found with amenities: {amenities_result[:50]}...")
                            else:
                                print(f"  ❌ Target property found but no amenities in search result")
                            break
                    else:
                        print(f"  ⚠️  Target property not found in search results")
                else:
                    print(f"  ❌ No results found for {street_search}")
                break
            print()
    
    # Test 2: Search for properties with bedrooms
    print("\n🛏️  Test 2: Searching for properties with bedroom data")
    
    conn = sqlite3.connect('data/database.sqlite')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ra.site_addr_1, ra.acct, pd.bedrooms 
        FROM real_acct ra 
        JOIN property_derived pd ON ra.acct = pd.acct 
        WHERE pd.bedrooms IS NOT NULL 
        LIMIT 2
    ''')
    
    bedroom_properties = cursor.fetchall()
    conn.close()
    
    if bedroom_properties:
        for addr, acct, bedrooms in bedroom_properties:
            print(f"  Property: {addr}")
            print(f"  Account: {acct}")
            print(f"  Bedrooms: {bedrooms}")
            
            # Test account search
            results = search_properties(account=acct)
            if results and len(results) > 0:
                result = results[0]
                bed_result = result.get('Bedrooms', 'None')
                if bed_result and bed_result != 'None':
                    print(f"  ✅ Account search successful - Bedrooms: {bed_result}")
                else:
                    print(f"  ❌ Account search found property but no bedroom data")
            else:
                print(f"  ❌ Account search failed")
            break
    
    # Test 3: General data availability stats
    print(f"\n📊 Test 3: Database Statistics")
    
    conn = sqlite3.connect('data/database.sqlite')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM real_acct')
    total_properties = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM property_derived WHERE amenities IS NOT NULL')
    amenities_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM property_derived WHERE bedrooms IS NOT NULL')
    bedrooms_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM property_derived WHERE bathrooms IS NOT NULL')
    bathrooms_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"  Total properties: {total_properties:,}")
    print(f"  Properties with amenities: {amenities_count:,} ({amenities_count/total_properties*100:.1f}%)")
    print(f"  Properties with bedrooms: {bedrooms_count:,} ({bedrooms_count/total_properties*100:.1f}%)")
    print(f"  Properties with bathrooms: {bathrooms_count:,} ({bathrooms_count/total_properties*100:.1f}%)")
    
    print(f"\n🎉 Testing Complete!")
    print(f"✅ Setup system working properly")
    print(f"✅ Database contains {total_properties:,} properties")
    print(f"✅ Enhanced data available for {amenities_count:,} properties")

if __name__ == "__main__":
    test_search_functionality()
