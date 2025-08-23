from __future__ import annotations
from typing import Dict, Any, Optional

MISSING_PENALTY_FACTOR = 0.5  # proportion of component weight applied when comp value missing
POOL_GARAGE_MISSING_FACTOR = 0.25  # smaller penalty for unknown pool/garage vs mismatch


def compute_score(record: Dict[str, Any], subject: Dict[str, Any], weights: Dict[str, float]) -> float:
    """Compute similarity score (0-100, higher is better).

    Components (each scaled by its weight):
      distance, size delta, year delta, beds diff, baths diff, stories diff,
      pool mismatch, garage mismatch.

    Previous logic ignored missing comparable attributes (no penalty) which
    allowed sparse records to rank artificially high. Now a missing attribute
    incurs a partial penalty (MISSING_PENALTY_FACTOR of that component's weight)
    so that complete records are favored. Pool/garage unknown is a smaller
    penalty than a definite mismatch.
    """
    penalties = 0.0
    base_im = _float(subject.get('building_area'))
    base_year = _int(subject.get('build_year'))
    base_beds = _float(subject.get('bedrooms'))
    base_baths = _float(subject.get('bathrooms'))
    base_stories = _int(subject.get('stories'))

    # Distance
    try:
        if record.get('distance_miles') is not None:
            penalties += weights.get('distance', 0.4) * min(1.0, float(record['distance_miles']) / 15.0)
    except Exception:
        pass

    # Size delta or missing
    try:
        if base_im is not None:
            if record.get('building_area') and record['building_area'] not in ('', '0'):
                sdelta = abs(float(record['building_area']) - base_im) / base_im
                penalties += weights.get('size', 0.25) * min(1.0, sdelta / 0.30)
            else:
                penalties += weights.get('size', 0.25) * MISSING_PENALTY_FACTOR
    except Exception:
        pass

    # Year delta or missing
    try:
        if base_year is not None:
            if record.get('build_year') and str(record.get('build_year')).isdigit():
                ydelta = abs(int(record['build_year']) - base_year)
                penalties += weights.get('year', 0.1) * min(1.0, ydelta / 15.0)
            else:
                penalties += weights.get('year', 0.1) * MISSING_PENALTY_FACTOR
    except Exception:
        pass

    # Beds diff or missing
    try:
        if base_beds is not None:
            if record.get('bedrooms') not in (None, ''):
                penalties += weights.get('beds_baths', 0.1) * (min(2.0, abs(float(record['bedrooms']) - base_beds)) / 2.0)
            else:
                penalties += weights.get('beds_baths', 0.1) * MISSING_PENALTY_FACTOR
    except Exception:
        pass

    # Baths diff or missing
    try:
        if base_baths is not None:
            if record.get('bathrooms') not in (None, ''):
                penalties += weights.get('beds_baths', 0.1) * (min(2.0, abs(float(record['bathrooms']) - base_baths)) / 2.0)
            else:
                penalties += weights.get('beds_baths', 0.1) * MISSING_PENALTY_FACTOR
    except Exception:
        pass

    # Stories diff or missing
    try:
        if base_stories is not None:
            if record.get('stories') not in (None, ''):
                penalties += weights.get('stories', 0.05) * min(1.0, abs(int(record['stories']) - int(base_stories)))
            else:
                penalties += weights.get('stories', 0.05) * MISSING_PENALTY_FACTOR
    except Exception:
        pass

    # Pool mismatch / missing
    try:
        subj_pool = subject.get('has_pool')
        if subj_pool in (0, 1):
            if record.get('has_pool') in (0, 1):
                if int(record['has_pool']) != int(subj_pool):
                    penalties += weights.get('pool_garage', 0.1) * 0.5
            else:
                penalties += weights.get('pool_garage', 0.1) * POOL_GARAGE_MISSING_FACTOR
    except Exception:
        pass

    # Garage mismatch / missing
    try:
        subj_garage = subject.get('has_garage')
        if subj_garage in (0, 1):
            if record.get('has_garage') in (0, 1):
                if int(record['has_garage']) != int(subj_garage):
                    penalties += weights.get('pool_garage', 0.1) * 0.5
            else:
                penalties += weights.get('pool_garage', 0.1) * POOL_GARAGE_MISSING_FACTOR
    except Exception:
        pass

    score = 100 * (1 - min(0.99, penalties))
    if score < 0:
        score = 0
    return round(score, 2)


def _float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if s == '' or s == '0':
            return None
        return float(s)
    except Exception:
        return None


def _int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s.isdigit():
            return None
        return int(s)
    except Exception:
        return None
