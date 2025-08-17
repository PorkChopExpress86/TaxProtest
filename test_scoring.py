from comparables.scoring import compute_score


def test_compute_score_no_penalties():
    subject = {
        'building_area': 2000,
        'build_year': 2010,
        'bedrooms': 4,
        'bathrooms': 3,
        'stories': 2,
        'has_pool': 1,
        'has_garage': 1,
    }
    comp = {
        'building_area': 2000,
        'build_year': 2010,
        'bedrooms': 4,
        'bathrooms': 3,
        'stories': 2,
        'has_pool': 1,
        'has_garage': 1,
        'distance_miles': 0.1,
    }
    weights = {'distance':0.0,'size':0.25,'year':0.1,'beds_baths':0.1,'stories':0.05,'pool_garage':0.1}
    score = compute_score(comp, subject, weights)
    assert score == 100.0


def test_compute_score_penalties():
    subject = {'building_area': 2000,'build_year': 2010,'bedrooms': 4,'bathrooms': 3,'stories': 2,'has_pool': 1,'has_garage': 1}
    comp = {'building_area': 2600,'build_year': 1995,'bedrooms': 6,'bathrooms': 5,'stories': 3,'has_pool': 0,'has_garage': 0,'distance_miles': 10}
    weights = {'distance':0.4,'size':0.25,'year':0.1,'beds_baths':0.1,'stories':0.05,'pool_garage':0.1}
    score = compute_score(comp, subject, weights)
    assert score < 100.0
    assert score >= 0

