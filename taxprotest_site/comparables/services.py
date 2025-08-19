# Small adapter to call the existing engine/search logic. Start by delegating to the legacy functions in src/taxprotest/comparables.
from typing import Any, Dict

try:
    from src.taxprotest.comparables.engine import find_comps as legacy_find_comps
except Exception:
    legacy_find_comps = None


def find_comps(subject_account: str, **kwargs) -> Dict[str, Any]:
    if legacy_find_comps:
        return legacy_find_comps(subject_account, **kwargs)
    raise RuntimeError("No compatible comparables engine available")
