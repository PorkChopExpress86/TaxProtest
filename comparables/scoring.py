from __future__ import annotations
from typing import Dict, Any, Optional

def compute_score(record: Dict[str, Any], subject: Dict[str, Any], weights: Dict[str,float]) -> float:
    """Compute similarity score (0-100, higher better) given a comparable and subject baselines.
    Penalizes distance, size delta, year delta, bed/bath differences, stories, and pool/garage mismatches.
    Missing data yields no penalty for that component.
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
            penalties += weights.get('distance',0.4) * min(1.0, float(record['distance_miles'])/15.0)
    except Exception:
        pass
    # Size
    try:
        if base_im and record.get('building_area') and record['building_area'] not in ('','0'):
            sdelta = abs(float(record['building_area'])-base_im)/base_im
            penalties += weights.get('size',0.25) * min(1.0, sdelta/0.30)
    except Exception:
        pass
    # Year
    try:
        if base_year and record.get('build_year') and str(record['build_year']).isdigit():
            ydelta = abs(int(record['build_year'])-base_year)
            penalties += weights.get('year',0.1) * min(1.0, ydelta/15.0)
    except Exception:
        pass
    # Beds / Baths
    try:
        if base_beds and record.get('bedrooms') not in (None,''):
            penalties += weights.get('beds_baths',0.1) * (min(2.0, abs(float(record['bedrooms'])-base_beds))/2.0)
    except Exception:
        pass
    try:
        if base_baths and record.get('bathrooms') not in (None,''):
            penalties += weights.get('beds_baths',0.1) * (min(2.0, abs(float(record['bathrooms'])-base_baths))/2.0)
    except Exception:
        pass
    # Stories
    try:
        if base_stories and record.get('stories') not in (None,''):
            penalties += weights.get('stories',0.05) * min(1.0, abs(int(record['stories'])-int(base_stories)))
    except Exception:
        pass
    # Pool / Garage mismatch penalties
    try:
        subj_pool = subject.get('has_pool')
        if subj_pool in (0,1) and record.get('has_pool') in (0,1) and int(record['has_pool']) != int(subj_pool):
            penalties += weights.get('pool_garage',0.1)*0.5
    except Exception:
        pass
    try:
        subj_garage = subject.get('has_garage')
        if subj_garage in (0,1) and record.get('has_garage') in (0,1) and int(record['has_garage']) != int(subj_garage):
            penalties += weights.get('pool_garage',0.1)*0.5
    except Exception:
        pass
    return round(100 * (1 - min(0.99, penalties)),2)

def _float(v: Any) -> Optional[float]:
    try:
        if v is None: return None
        s=str(v).strip()
        if s=='' or s=='0': return None
        return float(s)
    except Exception:
        return None

def _int(v: Any) -> Optional[int]:
    try:
        if v is None: return None
        s=str(v).strip()
        if not s.isdigit(): return None
        return int(s)
    except Exception:
        return None
