import sys
import unittest
import sqlite3
from pathlib import Path
import pytest
pytest.skip("Legacy duplicate test file; use tests/integration/test_wall_property.py", allow_module_level=True)

sys.path.append('.')

from extract_data import search_properties


class TestWallProperty(unittest.TestCase):
    DB_PATH = Path('data') / 'database.sqlite'

    def setUp(self):
        if not self.DB_PATH.exists():
            self.skipTest(f"Database not found at {self.DB_PATH}")
        self.conn = sqlite3.connect(str(self.DB_PATH))
        self.cur = self.conn.cursor()

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def test_16213_wall_st_has_derived_data(self):
        """Verify 16213 Wall St 77040 exists and has bedrooms/bathrooms or rating via search_properties"""
        # Find an account for the exact address pattern
        q = ("SELECT acct, site_addr_1, site_addr_3 FROM real_acct "
             "WHERE UPPER(site_addr_1) LIKE ? AND site_addr_3 LIKE ? LIMIT 1")
        self.cur.execute(q, ("%16213%WALL%", "%77040%"))
        row = self.cur.fetchone()
        self.assertIsNotNone(row, "Address 16213 Wall St 77040 not found in real_acct table")
        acct, addr, zipc = row
        results = search_properties(street="Wall St", zip_code="77040")
        self.assertTrue(results and len(results) > 0, "search_properties returned no results for Wall St 77040")
        match = next((r for r in results if r.get('Account Number') == acct), None)
        self.assertIsNotNone(match, f"Account {acct} not present in search results")
        bedrooms = match.get('Bedrooms')
        bathrooms = match.get('Bathrooms')
        prop_type = match.get('Property Type')
        self.assertEqual(bedrooms, 4, f"Expected 4 bedrooms for account {acct}, got {bedrooms}")
        try:
            bath_val = float(bathrooms) if bathrooms is not None else None
        except Exception:
            bath_val = None
        self.assertTrue(bath_val is not None and abs(bath_val-2.5) < 0.01, f"Expected 2.5 bathrooms for account {acct}, got {bath_val}")
        self.assertIn(prop_type, ('Residential', 'Residential Single-Family', None), f"Unexpected property type for account {acct}: {prop_type}")


if __name__ == '__main__':
    unittest.main()
