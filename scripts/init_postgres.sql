-- Postgres initialization (Phase 2)
-- Updated to include indexes for newly bulk‑loaded tables (owners, fixtures, extra_features, etc.).
-- Safe & idempotent: run after each refresh if desired.

-- Core indexes
CREATE INDEX IF NOT EXISTS idx_real_acct_acct ON real_acct(acct);
CREATE INDEX IF NOT EXISTS idx_building_res_acct ON building_res(acct);
CREATE INDEX IF NOT EXISTS idx_property_derived_acct ON property_derived(acct);
CREATE INDEX IF NOT EXISTS idx_real_acct_addr ON real_acct(site_addr_1);
CREATE INDEX IF NOT EXISTS idx_real_acct_zip ON real_acct(site_addr_3);

-- Property derived PPSF index (only if column exists)
DO $$
BEGIN
	IF EXISTS (
		SELECT 1 FROM information_schema.columns
		WHERE table_name = 'property_derived' AND column_name = 'ppsf'
	) THEN
		CREATE INDEX IF NOT EXISTS idx_property_derived_ppsf ON property_derived(ppsf);
	END IF;
END $$;

-- Phase 2: ancillary / supplemental tables now bulk loaded via COPY
CREATE INDEX IF NOT EXISTS idx_owners_acct ON owners(acct);
CREATE INDEX IF NOT EXISTS idx_fixtures_acct ON fixtures(acct);
CREATE INDEX IF NOT EXISTS idx_extra_features_acct ON extra_features(acct);
CREATE INDEX IF NOT EXISTS idx_building_other_acct ON building_other(acct);
CREATE INDEX IF NOT EXISTS idx_structural_elem1_acct ON structural_elem1(acct);
CREATE INDEX IF NOT EXISTS idx_structural_elem2_acct ON structural_elem2(acct);
CREATE INDEX IF NOT EXISTS idx_property_geo_acct ON property_geo(acct);

-- Optional future analytical indexes (commented until needed)
-- CREATE INDEX IF NOT EXISTS idx_property_derived_overall ON property_derived(overall_rating);
-- CREATE INDEX IF NOT EXISTS idx_property_derived_quality ON property_derived(quality_rating);

-- PostGIS enablement (safe if already enabled; ignore errors if extension not permitted)
CREATE EXTENSION IF NOT EXISTS postgis;
ALTER TABLE property_geo ADD COLUMN IF NOT EXISTS geom geometry(Point,4326);
UPDATE property_geo
	 SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude),4326)
 WHERE geom IS NULL
	 AND longitude IS NOT NULL AND latitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_property_geo_geom ON property_geo USING GIST (geom);
