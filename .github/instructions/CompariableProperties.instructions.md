# Property Comparison Instructions

> **Purpose:** Guide GitHub Copilot to generate production-ready code that finds **comparable single-family residential properties (SFR)** in **Harris County, TX**, suitable for **equal & uniform** appraisal analysis and basic valuation cross-checks.
> **Output:** a ranked set of comps + a median/percent-difference summary for the subject.

---

## 0) Assumptions & Data Schema

Copilot, assume a local **SQLite** (or Postgres) database with an **HCAD-like** table named `parcels` and (optionally) a `sales` table:

**`parcels` (minimum fields)**

- `account` (TEXT) – HCAD account ID (subject & comps)
- `land_use` (TEXT) – e.g., 'Single-Family Residential'
- `neighborhood_code` (TEXT) – HCAD neighborhood/market area code
- `address`, `city`, `zip` (TEXT)
- `lat`, `lon` (REAL) – WGS84 coordinates
- `living_area_sqft` (INTEGER)
- `lot_area_sqft` (INTEGER)
- `year_built` (INTEGER)
- `stories` (INTEGER or TEXT enum)
- `quality_class` (TEXT or INTEGER) – construction/quality grade if present
- `condition` (TEXT or INTEGER) – if present
- `bedrooms`, `bathrooms` (INTEGER) – if present
- `garage_spaces` (INTEGER) – if present
- `has_pool` (BOOLEAN/INTEGER) – if present
- `market_value` (INTEGER or REAL) – current HCAD market value (use for equity comps)
- `is_homestead` (BOOLEAN/INTEGER) – optional
- `is_new_construction` (BOOLEAN/INTEGER) – optional

**`sales` (optional; for reference only)**

- `account` (TEXT)
- `sale_date` (DATE)
- `sale_price` (REAL)
- `arms_length` (BOOLEAN/INTEGER)

> If a field does not exist, code must **gracefully skip** that filter/adjustment.

---

## 1) Inputs

Implement a function:

```python
def find_comps(
    subject_account: str,
    max_comps: int = 7,
    min_comps: int = 3,
    strategy: str = "equity",  # "equity" (assessed/market_value) or "sales" (if using sales table)
) -> dict:
    ...
```

- Load **subject** from `parcels` by `account`. If missing → raise a clear error.
- Use **subject’s market_value** (HCAD “market”) for equity analysis (ignore homestead caps for comparison).
- All numeric filters are **percent windows** around the subject (see Section 3).

---

## 2) Comparable Selection Logic (filters & fallbacks)

### 2.1 Base Required Filters

1. **Property type:** `land_use` must indicate **single-family residential** (case-insensitive match).
2. **Not the subject:** exclude `account == subject_account`.

### 2.2 Geographic Scope (tiered)

- **Tier G1 (strict):** same `neighborhood_code` if present on both subject and candidate.
- **Tier G2:** radial search using **Haversine** from subject `(lat, lon)`:
  - Start with **≤ 1.5 miles**.
  - If not enough comps, expand to **3 mi → 5 mi → 10 mi → 15 mi** (stop when `min_comps` met).
- If `lat/lon` missing, fall back to **same ZIP**; next, **same city**.

### 2.3 Physical Similarity Windows (strict → relaxed)

Define **configurable ranges** and **expand gradually** until `min_comps` is met.

- **Living area (improvement) – subject `A`:**
  - **S1:** ± **5%** of `A`
  - **S2:** ± **10%**
  - **S3:** ± **15%**
- **Lot area – subject `L`:**
  - **L1:** ± **10%**
  - **L2:** ± **20%**
  - **L3:** ± **30%**
- **Year built – subject `Y`:**
  - **Y1:** ± **5 years**
  - **Y2:** ± **10 years**
  - **Y3:** ± **15 years**
- **Stories:**
  - **T1:** exact match (e.g., 1-story vs 2-story)
  - **T2:** allow difference of **±1 story** if inventory low
- **Quality/Condition (if available):**
  - **Q1/C1:** same class/condition
  - **Q2/C2:** within **±1 class/grade** or adjacent condition bucket
- **Bedrooms/Bathrooms (if available):**
  - **B1:** bedrooms **±1**, baths **±1**
  - **B2:** relax to bedrooms **±2**, baths **±2**
- **Garage (if available):**
  - **G1:** garage presence must match (0 vs >0)
  - **G2:** allow difference of ±1 space
- **Pool (if available):**
  - **P1:** match presence
  - **P2:** ignore if inventory low

> Always **prefer S1/L1/Y1/T1/Q1/C1/B1/G1/P1**. Only expand to the next bands if you can’t hit `min_comps`.

---

## 3) Similarity Scoring & Ranking

... (content truncated for brevity in this example, but will include the full instructions above)
