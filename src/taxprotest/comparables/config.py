from __future__ import annotations
from typing import Sequence, Dict

SIZE_BANDS: Sequence[float | None] = [0.05, 0.10, 0.15, 0.20, 0.25, 0.35, None]
LOT_BANDS: Sequence[float | None] = [0.10, 0.20, 0.30, 0.40, 0.50, None]
YEAR_BANDS: Sequence[int | None] = [5, 10, 15, 20, 30, None]
BED_BATH_BANDS: Sequence[int | None] = [1, 2, 3, None]
RADIUS_TIERS: Sequence[float] = [1.5, 3, 5, 10, 15, 20, 25]
STORY_TOLERANCES = [0, 1, 2, None]

SCORING_WEIGHTS: Dict[str, float] = {
    'distance': 0.4,
    'size': 0.25,
    'year': 0.10,
    'beds_baths': 0.10,
    'stories': 0.05,
    'pool_garage': 0.10,
}

CACHE_MAX_ENTRIES = 50
