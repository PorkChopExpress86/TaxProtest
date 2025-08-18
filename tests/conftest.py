import pytest
import sys
from pathlib import Path
import sqlite3

# Ensure project root on path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
for p in (SRC, ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Directory ignoring now handled via pytest.ini (norecursedirs)

@pytest.fixture()
def minimal_engine_db(tmp_path):
    """Create minimal sqlite DB for engine tests and return path."""
    db_path = tmp_path / "engine_test.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE real_acct (acct TEXT PRIMARY KEY, site_addr_1 TEXT, site_addr_3 TEXT, tot_mkt_val REAL, land_ar REAL, Neighborhood_Code TEXT);
        CREATE TABLE building_res (acct TEXT, im_sq_ft REAL, eff INTEGER);
        CREATE TABLE property_derived (acct TEXT, bedrooms REAL, bathrooms REAL, amenities TEXT, property_type TEXT, overall_rating TEXT, quality_rating TEXT, rating_explanation TEXT, stories INTEGER, has_pool INTEGER, has_garage INTEGER);
        CREATE TABLE property_geo (acct TEXT, latitude REAL, longitude REAL);
        INSERT INTO real_acct VALUES ('S1','123 MAIN','77000',300000,5000,'N1');
        INSERT INTO building_res VALUES ('S1',2000,2005);
        INSERT INTO property_derived VALUES ('S1',3,2,'','R','Good','Avg','',2,1,1);
        INSERT INTO property_geo VALUES ('S1',29.7,-95.3);
        INSERT INTO real_acct VALUES ('C1','125 MAIN','77000',290000,4800,'N1');
        INSERT INTO building_res VALUES ('C1',1950,2006);
        INSERT INTO property_derived VALUES ('C1',3,2,'','R','Good','Avg','',2,1,1);
        INSERT INTO property_geo VALUES ('C1',29.7005,-95.3005);
        INSERT INTO real_acct VALUES ('C2','127 MAIN','77000',310000,5200,'N1');
        INSERT INTO building_res VALUES ('C2',2050,2004);
        INSERT INTO property_derived VALUES ('C2',3,2,'','R','Good','Avg','',2,1,1);
        INSERT INTO property_geo VALUES ('C2',29.7010,-95.3010);
        """
    )
    conn.commit(); conn.close()
    return str(db_path)
