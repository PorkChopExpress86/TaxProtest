from __future__ import annotations

from typing import List, Dict, Any
import csv, os, datetime, logging

DEFAULT_EXPORT_DIR = "Exports"
logger = logging.getLogger(__name__)


def export_comparables(
    subject: Dict[str, Any],
    comps: List[Dict[str, Any]],
    out_dir: str | None = None,
    fmt: str = "csv",
) -> str:
    """Export comparable property data.

    Args:
        subject: Subject property record.
        comps: List of comparable property dicts.
        out_dir: Output directory (created if missing) default 'Exports'.
        fmt: 'csv' (default) or 'xlsx' (requires pandas + openpyxl or xlsxwriter).

    Returns:
        Path to generated export file.
    """
    if out_dir is None:
        out_dir = DEFAULT_EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"comparables_{subject.get('account') or subject.get('acct') or 'subject'}_{timestamp}"

    # Column ordering – prefer key analytical columns first, then remaining sorted.
    fieldnames = sorted({k for c in comps for k in c.keys()})
    preferred = [
        "account",
        "acct",
        "market_value",
        "Market Value",
        "living_area",
        "Building Area",
        "land_area",
        "Land Area",
        "year_built",
        "Build Year",
        "ppsf",
        "Price Per Sq Ft",
        "distance",
        "Distance Miles",
        "score",
    ]
    ordered = []
    seen = set()
    for col in preferred:
        if col in fieldnames and col not in seen:
            ordered.append(col)
            seen.add(col)
    for col in fieldnames:
        if col not in seen:
            ordered.append(col)

    fmt = fmt.lower()
    if fmt == "xlsx":
        try:
            import pandas as pd  # type: ignore

            df = pd.DataFrame(comps)
            # Reorder columns if present
            df = df[[c for c in ordered if c in df.columns]]
            xlsx_path = os.path.join(out_dir, base + ".xlsx")
            # Attempt write with default engine; fallback to csv on failure.
            try:
                df.to_excel(xlsx_path, index=False)
                return xlsx_path
            except Exception as e:  # pragma: no cover - fallback path
                logger.warning("XLSX export failed (%s); falling back to CSV", e)
                # Continue to CSV below
        except Exception:  # pragma: no cover - pandas not installed
            logger.info("pandas not available; falling back to CSV export")
        fmt = "csv"  # ensure CSV fallback

    csv_path = os.path.join(out_dir, base + ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        for row in comps:
            writer.writerow(row)
    return csv_path
