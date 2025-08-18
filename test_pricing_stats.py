import pytest
pytest.skip("Legacy duplicate test file; use tests/unit/test_pricing_stats.py", allow_module_level=True)

from taxprotest.comparables.stats import compute_pricing_stats  # renamed duplicate (legacy)


def test_compute_pricing_stats_empty():
    subject = {'market_value': None, 'ppsf': None, 'has_pool': None, 'has_garage': None}
    res = compute_pricing_stats(subject, [])
    assert res['value_stats']['count'] == 0
    assert res['ppsf_stats']['count'] == 0


def test_compute_pricing_stats_basic():
    subject = {'market_value': 300000, 'ppsf': 150, 'has_pool': 1, 'has_garage': 1}
    comps = [
        {'market_value': 290000, 'ppsf': 145, 'has_pool': 1, 'has_garage': 1},
        {'market_value': 310000, 'ppsf': 155, 'has_pool': 1, 'has_garage': 0},
        {'market_value': 305000, 'ppsf': 160, 'has_pool': 0, 'has_garage': 1},
    ]
    res = compute_pricing_stats(subject, comps)
    assert res['value_stats']['count'] == 3
    assert res['ppsf_stats']['count'] == 3
    # Median value should be middle value (305000)
    assert res['value_stats']['median'] == 305000
    # PPSF band count within 10% of subject (135 to 165) should equal all 3 comps
    assert res['ppsf_band_counts']['within_10pct'] == 3
    # Pool match rate should be fraction with pool = 2/3 -> 66.67 approx
    assert round(res['pool_match_rate'],2) in (66.67, 66.66)

