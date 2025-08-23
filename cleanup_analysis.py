"""
File Cleanup Analysis
===================

KEEP (Useful debugging/utility files):
- check_import_results.py - Useful for verifying database state
- test_extraction.py - Good for testing extraction logic
- scripts/extract_gis_nested.py - May be needed for GIS processing
- scripts/refresh_data.ps1 - Utility script

DELETE (Temporary/obsolete debugging files):
- check_account_match.py - Debug file for account format issues (now fixed)
- check_all_databases.py - One-time debugging
- check_amenities.py - Superseded by integrated solution
- check_amenities2.py - Duplicate debugging file
- check_missing_accounts.py - One-time debugging
- check_tables.py - One-time debugging
- check_user_search.py - One-time debugging
- check_wall_st_account.py - Specific debugging for Wall St issue
- check_wall_st_specific.py - Specific debugging for Wall St issue
- comprehensive_amenities_test.py - Superseded by test_complete_setup.py
- fast_amenities_update.py - Obsolete approach
- final_verification.py - Superseded by test_complete_setup.py
- find_amenities_addresses.py - One-time debugging
- regenerate_complete.py - Obsolete approach
- regenerate_fixed.py - Obsolete approach
- regenerate_with_amenities.py - Obsolete approach
- test_amenities_quick.py - One-time debugging
- test_search_amenities.py - One-time debugging
- test_specific_account.py - One-time debugging
- wall_st_analysis.py - One-time debugging

TOTAL FILES TO DELETE: 18
"""

files_to_delete = [
    "check_account_match.py",
    "check_all_databases.py", 
    "check_amenities.py",
    "check_amenities2.py",
    "check_missing_accounts.py",
    "check_tables.py",
    "check_user_search.py",
    "check_wall_st_account.py",
    "check_wall_st_specific.py",
    "comprehensive_amenities_test.py",
    "fast_amenities_update.py",
    "final_verification.py",
    "find_amenities_addresses.py",
    "regenerate_complete.py",
    "regenerate_fixed.py", 
    "regenerate_with_amenities.py",
    "test_amenities_quick.py",
    "test_search_amenities.py",
    "test_specific_account.py",
    "wall_st_analysis.py"
]

print(f"Files identified for deletion: {len(files_to_delete)}")
for f in files_to_delete:
    print(f"  {f}")
