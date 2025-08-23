import pytest
pytest.skip("Legacy duplicate test file; use tests/integration/test_comparables_wall.py", allow_module_level=True)

import unittest, sqlite3
from extract_data import find_comparables, find_comparables_debug

TARGET_ACCT = '1074380000028'

class TestComparablesForWall(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect('data/database.sqlite')
        self.cur = self.conn.cursor()

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def test_subject_exists(self):
        self.cur.execute('SELECT acct FROM real_acct WHERE acct=?', (TARGET_ACCT,))
        self.assertIsNotNone(self.cur.fetchone(), f'Subject {TARGET_ACCT} missing in real_acct')

    def test_comparables_diagnostics(self):
        diag = find_comparables_debug(TARGET_ACCT, max_distance_miles=5.0)
        # Always assert diagnostic keys present
        expected_keys = {'base_found','base_has_geo','base_building_area','base_land_area','bbox_candidates','filtered_size','filtered_land','within_distance','reason'}
        self.assertTrue(expected_keys.issubset(diag.keys()))
        if not diag['base_has_geo']:
            self.fail(f"No geo for subject {TARGET_ACCT}: {diag['reason']}")
        if diag['bbox_candidates'] == 0:
            self.fail(f"No candidates in bbox: {diag}")
        if diag['within_distance'] == 0:
            self.fail(f"All candidates filtered out: {diag}")

    def test_find_comparables_result_or_reason(self):
        comps = find_comparables(TARGET_ACCT, max_distance_miles=5.0)
        if not comps:
            diag = find_comparables_debug(TARGET_ACCT, max_distance_miles=5.0)
            self.fail(f"No comparables returned. Diagnostics: {diag}")
        # Basic sanity on first comp
        first = comps[0]
        self.assertIn('Distance Miles', first)
        self.assertIn('Market Value', first)

if __name__ == '__main__':
    unittest.main()
