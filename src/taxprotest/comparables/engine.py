from __future__ import annotations
import sqlite3
import math
from itertools import product
from typing import Dict, Any, List, Optional, Tuple, Iterable, Callable

from .stats import compute_pricing_stats
from .scoring import compute_score
from .config import (
    SIZE_BANDS,
    LOT_BANDS,
    YEAR_BANDS,
    BED_BATH_BANDS,
    RADIUS_TIERS,
    STORY_TOLERANCES,
    SCORING_WEIGHTS,
    CACHE_MAX_ENTRIES,
)

_CACHE: list[tuple[tuple, dict]] = []  # simple LRU list [(key, value), ...]

def _cache_get(key: tuple):
    if CACHE_MAX_ENTRIES <= 0:
        return None
    for i,(k,v) in enumerate(_CACHE):
        if k == key:
            # move to front (MRU)
            _CACHE.insert(0, _CACHE.pop(i))
            return v
    return None

def _cache_set(key: tuple, value: dict):
    if CACHE_MAX_ENTRIES <= 0:
        return
    # remove existing
    for i,(k,_) in enumerate(_CACHE):
        if k == key:
            _CACHE.pop(i)
            break
    _CACHE.insert(0,(key,value))
    if len(_CACHE) > CACHE_MAX_ENTRIES:
        _CACHE.pop()

DB_PATH = None  # Will be set by application using set_db_path

def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path

# Helper numeric conversions

def _float(v: Any) -> Optional[float]:
    try:
        if v is None: return None
        s=str(v).strip()
        if s in ('','0'): return None
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

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def find_comps(
    subject_account: str,
    max_comps: int = 25,
    min_comps: int = 20,
    strategy: str = "equity",  # strategy kept for future diversification; presently unused.
    radius_first_strict: bool = False,
    max_radius: float | None = None,
) -> Dict[str, Any]:
    if DB_PATH is None:
        import os
        from pathlib import Path
        DB_PATH_local = Path(os.path.abspath(os.path.dirname(__file__))).parent / 'data' / 'database.sqlite'
    else:
        DB_PATH_local = DB_PATH
    conn = sqlite3.connect(DB_PATH_local)
    cur = conn.cursor()
    try:
        # Load subject row
        subject_sql = """SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft, br.eff,
                                 pd.bedrooms, pd.bathrooms, pd.amenities, pd.property_type, pd.overall_rating, pd.quality_rating,
                                 pd.rating_explanation, pg.latitude, pg.longitude, ra.Neighborhood_Code,
                                 pd.stories, pd.has_pool, pd.has_garage
                          FROM real_acct ra
                          LEFT JOIN building_res br ON ra.acct = br.acct
                          LEFT JOIN property_derived pd ON ra.acct = pd.acct
                          LEFT JOIN property_geo pg ON ra.acct = pg.acct
                          WHERE ra.acct = ?"""
        cur.execute(subject_sql, (subject_account,))
        srow = cur.fetchone()
        if not srow:
            raise ValueError(f"Subject account {subject_account} not found")
        (acct, addr1, zipc, mval, land_ar, im_sq_ft, eff_year, s_beds, s_baths, s_amen, s_type, s_overall, s_quality,
         s_rating_expl, s_lat, s_lon, s_nbhd, s_stories, s_has_pool, s_has_garage) = srow
        subject: Dict[str, Any] = {
            'acct': acct,
            'site_addr_1': addr1,
            'site_addr_3': zipc,
            'market_value': mval,
            'land_area': land_ar,
            'building_area': im_sq_ft,
            'build_year': eff_year,
            'bedrooms': s_beds,
            'bathrooms': s_baths,
            'amenities': s_amen,
            'property_type': s_type,
            'overall_rating': s_overall,
            'quality_rating': s_quality,
            'rating_explanation': s_rating_expl,
            'stories': s_stories,
            'has_pool': s_has_pool,
            'has_garage': s_has_garage,
            'latitude': s_lat,
            'longitude': s_lon,
        }
        try:
            if im_sq_ft and im_sq_ft not in ('','0') and mval and mval not in ('','0'):
                subject['ppsf'] = round(float(mval)/float(im_sq_ft), 2)
        except Exception:
            pass

        # Base numeric references
        base_im = _float(im_sq_ft)
        base_lot = _float(land_ar)
        base_year = _int(eff_year)
        base_beds = _float(s_beds)
        base_baths = _float(s_baths)

        # Constraint bands (copy so we can filter)
        size_bands = list(SIZE_BANDS)
        lot_bands = list(LOT_BANDS)
        year_bands = list(YEAR_BANDS)
        bed_bath_bands = list(BED_BATH_BANDS)
        radius_tiers = list(RADIUS_TIERS)
        if max_radius is not None:
            try:
                radius_tiers = [r for r in radius_tiers if r <= float(max_radius)] or radius_tiers
            except Exception:
                pass
        story_tolerances = list(STORY_TOLERANCES) if (s_stories is not None and str(s_stories).strip() != '') else [None]
        pool_modes = ['match', 'any'] if s_has_pool in (0, 1) else ['any']
        garage_modes = ['match', 'any'] if s_has_garage in (0, 1) else ['any']

        chosen_meta: Dict[str, Any] = {
            'geo_tier': None,
            'radius_miles': None,
            'size_band': None,
            'lot_band': None,
            'year_band': None,
            'bed_bath_band': None,
            'story_band': None,
            'pool_rule': None,
            'garage_rule': None,
            'attempts': 0,
            'subject_has_geo': bool(s_lat is not None and s_lon is not None),
            'used_neighborhood': False,
            'scoring_weights': SCORING_WEIGHTS.copy(),
        }
        baseline_story = '±0' if (s_stories is not None and str(s_stories).strip() != '') else 'any'
        baseline_meta_labels = {
            'size_band': '±5%',
            'lot_band': '±10%',
            'year_band': '±5y',
            'bed_bath_band': '±1',
            'story_band': baseline_story,
            'pool_rule': 'match',
            'garage_rule': 'match',
        }

        def passes(candidate, size_band, lot_band, year_band, bed_bath_band, story_tol, pool_mode, garage_mode):
            (c_acct, c_addr1, c_zipc, c_mval, c_land_ar, c_im_sq_ft, c_eff_year, c_beds, c_baths,
             c_amen, c_type, c_overall, c_quality, c_rating_expl, c_lat, c_lon, c_stories, c_pool, c_garage) = candidate
            if size_band is not None and base_im and c_im_sq_ft and c_im_sq_ft not in ('','0'):
                try:
                    cim = float(c_im_sq_ft)
                    if cim < base_im*(1-size_band) or cim > base_im*(1+size_band):
                        return False
                except Exception:
                    return False
            if lot_band is not None and base_lot and c_land_ar and c_land_ar not in ('','0'):
                try:
                    clot = float(c_land_ar)
                    if clot < base_lot*(1-lot_band) or clot > base_lot*(1+lot_band):
                        return False
                except Exception:
                    return False
            if year_band is not None and base_year and c_eff_year and str(c_eff_year).isdigit():
                try:
                    cy = int(c_eff_year)
                    if abs(cy - base_year) > year_band:
                        return False
                except Exception:
                    return False
            if bed_bath_band is not None:
                if base_beds is not None and c_beds not in (None, ''):
                    try:
                        if abs(float(c_beds) - base_beds) > bed_bath_band:
                            return False
                    except Exception:
                        return False
                if base_baths is not None and c_baths not in (None, ''):
                    try:
                        if abs(float(c_baths) - base_baths) > bed_bath_band:
                            return False
                    except Exception:
                        return False
            if story_tol is not None and s_stories is not None and str(s_stories).strip() != '':
                if c_stories in (None, ''):
                    return False
                try:
                    if abs(int(c_stories) - int(s_stories)) > story_tol:
                        return False
                except Exception:
                    return False
            if pool_mode == 'match' and s_has_pool in (0, 1) and c_pool in (0, 1) and int(c_pool) != int(s_has_pool):
                return False
            if garage_mode == 'match' and s_has_garage in (0, 1) and c_garage in (0, 1) and int(c_garage) != int(s_has_garage):
                return False
            return True

        base_select = """SELECT ra.acct, ra.site_addr_1, ra.site_addr_3, ra.tot_mkt_val, ra.land_ar, br.im_sq_ft, br.eff,
                                   pd.bedrooms, pd.bathrooms, pd.amenities, pd.property_type, pd.overall_rating, pd.quality_rating,
                                   pd.rating_explanation, pg.latitude, pg.longitude, pd.stories, pd.has_pool, pd.has_garage
                            FROM real_acct ra
                            LEFT JOIN building_res br ON ra.acct = br.acct
                            LEFT JOIN property_derived pd ON ra.acct = pd.acct
                            LEFT JOIN property_geo pg ON ra.acct = pg.acct"""

        def neighborhood_candidates():
            if not s_nbhd or str(s_nbhd).strip() == '':
                return []
            cur.execute(base_select + " WHERE ra.acct <> ? AND ra.Neighborhood_Code = ?", (subject_account, s_nbhd))
            return cur.fetchall()

        def radius_candidates(radius):
            if not (s_lat and s_lon):
                return []
            deg = radius/69.0
            cur.execute(base_select + " WHERE ra.acct <> ? AND pg.latitude BETWEEN ? AND ? AND pg.longitude BETWEEN ? AND ?",
                        (subject_account, s_lat - deg, s_lat + deg, s_lon - deg, s_lon + deg))
            return cur.fetchall()

        def zip_candidates():
            if not zipc:
                return []
            cur.execute(base_select + " WHERE ra.acct <> ? AND ra.site_addr_3 = ?", (subject_account, zipc))
            return cur.fetchall()

        geo_sequences: List[Tuple[str, Optional[float], Any]] = []
        if s_nbhd and str(s_nbhd).strip() != '':
            geo_sequences.append(('neighborhood', None, neighborhood_candidates))
        if s_lat and s_lon:
            for r in radius_tiers:
                geo_sequences.append(('radius', r, lambda rr=r: radius_candidates(rr)))
        geo_sequences.append(('zip', None, zip_candidates))

        cache_key = (subject_account, max_comps, min_comps, radius_first_strict, max_radius)
        cached = _cache_get(cache_key)
        if cached:
            return cached

        attempts = 0

        def build_dist_map(candidates_all):
            if not (s_lat and s_lon):
                return {}
            out = {}
            for cand in candidates_all:
                c_lat, c_lon = cand[14], cand[15]
                if c_lat is not None and c_lon is not None:
                    try:
                        out[cand[0]] = haversine(float(s_lat), float(s_lon), float(c_lat), float(c_lon))
                    except Exception:
                        pass
            return out

        def materialize_candidate(cand, dist_map, radius_val):
            (c_acct, c_addr1, c_zipc, c_mval, c_land_ar, c_im_sq_ft, c_eff_year, c_beds, c_baths,
             c_amen, c_type, c_overall, c_quality, c_rating_expl, c_lat, c_lon, c_stories, c_pool, c_garage) = cand
            if radius_val is not None and s_lat and s_lon and c_acct in dist_map and dist_map[c_acct] > radius_val:
                return None
            rec = {
                'acct': c_acct,
                'site_addr_1': c_addr1,
                'site_addr_3': c_zipc,
                'market_value': c_mval,
                'land_area': c_land_ar,
                'building_area': c_im_sq_ft,
                'build_year': c_eff_year,
                'bedrooms': c_beds,
                'bathrooms': c_baths,
                'stories': c_stories,
                'has_pool': c_pool,
                'has_garage': c_garage,
                'amenities': c_amen,
                'property_type': c_type,
                'overall_rating': c_overall,
                'quality_rating': c_quality,
                'rating_explanation': c_rating_expl,
                'distance_miles': round(dist_map.get(c_acct, 0.0), 2) if c_acct in dist_map else None,
            }
            try:
                if c_im_sq_ft and c_im_sq_ft not in ('','0') and c_mval and c_mval not in ('','0'):
                    rec['ppsf'] = round(float(c_mval)/float(c_im_sq_ft), 2)
            except Exception:
                pass
            return rec

        def finalize_result(comps: List[Dict[str, Any]], geo_label, radius_val,
                             size_band, lot_band, year_band, bed_bath_band, story_tol, pool_mode, garage_mode, attempts):
            chosen_meta.update({
                'geo_tier': geo_label,
                'radius_miles': radius_val,
                'size_band': ('any' if size_band is None else f"±{int(size_band*100)}%"),
                'lot_band': ('any' if lot_band is None else f"±{int(lot_band*100)}%"),
                'year_band': ('any' if year_band is None else f"±{year_band}y"),
                'bed_bath_band': ('any' if bed_bath_band is None else f"±{bed_bath_band}"),
                'story_band': ('any' if story_tol is None else f"±{story_tol}"),
                'pool_rule': pool_mode,
                'garage_rule': garage_mode,
                'attempts': attempts,
                'used_neighborhood': geo_label == 'neighborhood',
            })
            for r in comps:
                r['score'] = compute_score(r, subject, chosen_meta['scoring_weights'])
            comps.sort(key=lambda r: (-r['score'], r.get('distance_miles') if r.get('distance_miles') is not None else 9999))
            chosen_meta['baseline'] = baseline_meta_labels
            chosen_meta['relaxed'] = {k: (chosen_meta.get(k) != v) for k, v in baseline_meta_labels.items()}
            chosen_meta['pricing_stats'] = compute_pricing_stats(subject, comps)
            result = {'subject': subject, 'comps': comps, 'meta': chosen_meta}
            _cache_set(cache_key, result)
            return result

        for geo_label, radius_val, producer in geo_sequences:
            candidates_all = producer()
            dist_map = build_dist_map(candidates_all)

            def iterate_constraint_sets():
                if radius_first_strict:
                    yield (
                        size_bands[0],
                        lot_bands[0],
                        year_bands[0],
                        bed_bath_bands[0],
                        story_tolerances[0],
                        pool_modes[0],
                        garage_modes[0],
                        True,
                    )
                for combo in product(
                    size_bands,
                    lot_bands,
                    year_bands,
                    bed_bath_bands,
                    story_tolerances,
                    pool_modes,
                    garage_modes,
                ):
                    yield (*combo, False)

            seen_strict = False
            for size_band, lot_band, year_band, bed_bath_band, story_tol, pool_mode, garage_mode, is_strict in iterate_constraint_sets():
                if is_strict:
                    seen_strict = True
                elif radius_first_strict and not seen_strict:
                    continue
                attempts += 1
                selected: List[Dict[str, Any]] = []
                for cand in candidates_all:
                    if passes(cand, size_band, lot_band, year_band, bed_bath_band, story_tol, pool_mode, garage_mode):
                        rec = materialize_candidate(cand, dist_map, radius_val)
                        if rec is None:
                            continue
                        selected.append(rec)
                        if len(selected) >= max_comps:
                            break
                if len(selected) >= min_comps:
                    return finalize_result(selected, geo_label, radius_val, size_band, lot_band, year_band,
                                            bed_bath_band, story_tol, pool_mode, garage_mode, attempts)

        chosen_meta['attempts'] = attempts
        chosen_meta['baseline'] = baseline_meta_labels
        chosen_meta['relaxed'] = {k: (chosen_meta.get(k) != v) for k, v in baseline_meta_labels.items()}
        chosen_meta['pricing_stats'] = compute_pricing_stats(subject, [])
        result = {'subject': subject, 'comps': [], 'meta': chosen_meta}
        _cache_set(cache_key, result)
        return result
    finally:
        cur.close(); conn.close()
