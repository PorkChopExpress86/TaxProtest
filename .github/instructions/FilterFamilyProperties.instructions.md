# Filtering HCAD Data for Residential (Family-Livable) Properties

This document describes how to filter Harris County Appraisal District (HCAD) data to include **only residential properties** where families would live, while excluding commercial, industrial, agricultural, and personal business properties.

---

## 1. Use the Correct Data Sources
- **Include**:
  - `real_acct.txt` → Parcel/account level information.
  - `building_res.txt` → Residential buildings and improvements.
  - `land.txt` → Land use codes.
- **Exclude**:
  - `building_other.txt` → Commercial/income-producing buildings.
  - `t_business_acct.txt` and related personal property files.

---

## 2. Filter by State Class (Property Use Code)
- Each record in `real_acct.txt` and `building_res.txt` has a `state_class` or `property_use_cd`.
- These codes map to descriptions in `desc_r_01_state_class.txt`.
- Residential codes include:
  - **Single Family Homes**: e.g., A1, A2, A3.
  - **Townhomes/Condos**: Residential style codes.
  - **Multi-Family (optional)**: Apartments (if desired).
- Exclude:
  - Commercial, industrial, exempt, and agricultural codes.

---

## 3. Distinguish Residential vs Commercial Buildings
- `building_res.txt` = Residential improvements (houses, condos, townhomes, apartments).
- `building_other.txt` = Non-residential (office, retail, warehouses, etc.).
- Restrict analysis to **`building_res.txt` joined with `real_acct.txt`**.

---

## 4. Apply Land Use Codes
- Land use codes in `land.txt` (`use_cd`, linked to `desc_r_15_land_usecode.txt`):
  - **1000** = Residential Vacant Land
  - **1001** = Residential Improved (house built)
  - **2001** = Residential use (manual override)
- Exclude:
  - Agricultural, commercial, or exempt codes.

---

## 5. Practical Filtering Rules
1. Keep parcels that:
   - Appear in `building_res.txt`.
   - AND have a residential `state_class` (single-family, townhome, condo, optionally multifamily).
2. Drop parcels that:
   - Appear only in `building_other.txt`.
   - OR have commercial/industrial/agricultural `state_class`.
   - OR are listed in business personal property files.

---

## Summary
By combining **state class filters, building file selection, and land use codes**, you can isolate **residential family-livable properties** in Harris County and exclude commercial and other non-residential properties.
