import unittest
import sqlite3

class TestPropertyType(unittest.TestCase):

    DB_PATH = 'e:/TaxProtest/data/database.sqlite'

    def setUp(self):
        """Set up database connection."""
        self.conn = sqlite3.connect(self.DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """Close database connection."""
        self.cursor.close()
        self.conn.close()

    def test_wall_st_properties(self):
        """Test that all properties on Wall St in ZIP 77040 with area > 0 are single-family homes."""
        query = """
        SELECT pd.acct, pd.property_type, ra.site_addr_1, ra.site_addr_3, br.im_sq_ft
        FROM property_derived pd
        JOIN real_acct ra ON pd.acct = ra.acct
        JOIN building_res br ON pd.acct = br.acct
        WHERE ra.site_addr_1 LIKE '%WALL ST%'
          AND ra.site_addr_3 = '77040'
          AND br.im_sq_ft > 0;
        """
        self.cursor.execute(query)
        results = self.cursor.fetchall()

        for acct, property_type, address, zip_code, area in results:
            with self.subTest(acct=acct):
                self.assertEqual(property_type, 'Residential Single-Family',
                                 f"Property {acct} at {address}, {zip_code} with area {area} should be 'Residential Single-Family', but got '{property_type}'")

    def test_building_res_schema(self):
        """Check the schema of the building_res table."""
        query = "PRAGMA table_info(building_res);"
        self.cursor.execute(query)
        schema = self.cursor.fetchall()
        for column in schema:
            print(column)

if __name__ == '__main__':
    unittest.main()
