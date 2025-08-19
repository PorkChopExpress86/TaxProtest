"""Deprecated legacy module; use 'taxprotest.comparables.export'.
Retained temporarily for backward import compatibility."""
from __future__ import annotations
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import csv

from .engine import find_comps

# Export directory expected to be created by application root

def export_comparables(subject_account: str,
                       max_comps: int = 25,
                       min_comps: int = 20,
                       radius_first_strict: bool = False,
                       max_radius: float | None = None,
                       file_format: str = 'xlsx',
                       exports_dir: Path | None = None) -> str:
    """Generate an export file (Excel or CSV) for the current comparables set.

    Returns path to created file. Caller is responsible for cleanup.
    """
    from .stats import compute_pricing_stats  # local import to avoid circular
    from datetime import datetime
    res = find_comps(subject_account,
                     max_comps=max_comps,
                     min_comps=min_comps,
                     radius_first_strict=radius_first_strict,
                     max_radius=max_radius)
    subject = res.get('subject') or {}
    comps: List[Dict[str, Any]] = res.get('comps', [])
    meta: Dict[str, Any] = res.get('meta', {})
    rows: List[Dict[str, Any]] = []
    for c in comps:
        rows.append({
            'Account': c.get('acct'),
            'Score': c.get('score'),
            'Address': f"{c.get('site_addr_1','')} {c.get('site_addr_3','')}".strip(),
            'Market Value': c.get('market_value'),
            'Building Area': c.get('building_area'),
            'Land Area': c.get('land_area'),
            'PPSF': c.get('ppsf'),
            'Year': c.get('build_year'),
            'Bedrooms': c.get('bedrooms'),
            'Bathrooms': c.get('bathrooms'),
            'Stories': c.get('stories'),
            'Pool': c.get('has_pool'),
            'Garage': c.get('has_garage'),
            'Distance (mi)': c.get('distance_miles'),
            'Amenities': c.get('amenities'),
        })
    # Default export dir
    if exports_dir is None:
        from pathlib import Path
        exports_dir = Path(__file__).resolve().parent.parent / 'Exports'
    exports_dir.mkdir(exist_ok=True)
    geo_tag = meta.get('geo_tier') or 'geo'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"comparables_{subject_account}_{geo_tag}_{timestamp}.{ 'csv' if file_format=='csv' else 'xlsx'}"
    out_path = exports_dir / fname
    if file_format == 'csv':
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            headers = list(rows[0].keys()) if rows else []
            writer.writerow(headers)
            for r in rows:
                writer.writerow([r.get(h) for h in headers])
        return str(out_path)
    # Excel
    try:
        import pandas as pd  # type: ignore
        df = pd.DataFrame(rows)
        meta_df = pd.DataFrame([(k, str(v)) for k,v in meta.items()], columns=['Metric','Value'])
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:  # type: ignore
            df.to_excel(writer, index=False, sheet_name='Comparables')
            meta_df.to_excel(writer, index=False, sheet_name='Meta')
            if subject:
                subj_df = pd.DataFrame([(k, str(v)) for k,v in subject.items()], columns=['Field','Value'])
                subj_df.to_excel(writer, index=False, sheet_name='Subject')
            pricing = meta.get('pricing_stats')
            if isinstance(pricing, dict) and pricing:
                flat: List[tuple[str, Any]] = []
                for section_key, section_val in pricing.items():
                    if isinstance(section_val, dict):
                        for k,v in section_val.items():
                            flat.append((f"{section_key}.{k}", v))
                    else:
                        flat.append((section_key, section_val))
                pd.DataFrame(flat, columns=['Metric','Value']).to_excel(writer, index=False, sheet_name='PricingStats')
        return str(out_path)
    except Exception:
        csv_path = out_path.with_suffix('.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            headers = list(rows[0].keys()) if rows else []
            writer.writerow(headers)
            for r in rows:
                writer.writerow([r.get(h) for h in headers])
        return str(csv_path)
