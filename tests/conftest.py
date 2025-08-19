import pytest
import sys
from pathlib import Path
import sqlite3
import os

try:
    from db import get_connection
except Exception:  # fallback if import path issues
    get_connection = None  # type: ignore

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
    """Create minimal DB for engine tests and return a connection string path.

    If TAXPROTEST_DATABASE_URL points to Postgres, use that and load test data there.
    Otherwise create a temporary SQLite file as before.
    """
    pg_url = os.getenv("TAXPROTEST_DATABASE_URL")
    schema_sql = """
        CREATE TABLE IF NOT EXISTS real_acct (acct TEXT PRIMARY KEY, site_addr_1 TEXT, site_addr_3 TEXT, tot_mkt_val REAL, land_ar REAL, Neighborhood_Code TEXT);
        CREATE TABLE IF NOT EXISTS building_res (acct TEXT, im_sq_ft REAL, eff INTEGER);
        CREATE TABLE IF NOT EXISTS property_derived (acct TEXT, bedrooms REAL, bathrooms REAL, amenities TEXT, property_type TEXT, overall_rating TEXT, quality_rating TEXT, rating_explanation TEXT, stories INTEGER, has_pool INTEGER, has_garage INTEGER, ppsf REAL);
        CREATE TABLE IF NOT EXISTS property_geo (acct TEXT, latitude REAL, longitude REAL);
    """
    data_sql = [
        "INSERT INTO real_acct (acct, site_addr_1, site_addr_3, tot_mkt_val, land_ar, Neighborhood_Code) VALUES ('S1','123 MAIN','77000',300000,5000,'N1')",
        "INSERT INTO building_res VALUES ('S1',2000,2005)",
        "INSERT INTO property_derived (acct, bedrooms, bathrooms, amenities, property_type, overall_rating, quality_rating, rating_explanation, stories, has_pool, has_garage, ppsf) VALUES ('S1',3,2,'','R','Good','Avg','',2,1,1,NULL)",
        "INSERT INTO property_geo VALUES ('S1',29.7,-95.3)",
        "INSERT INTO real_acct VALUES ('C1','125 MAIN','77000',290000,4800,'N1')",
        "INSERT INTO building_res VALUES ('C1',1950,2006)",
        "INSERT INTO property_derived VALUES ('C1',3,2,'','R','Good','Avg','',2,1,1,NULL)",
        "INSERT INTO property_geo VALUES ('C1',29.7005,-95.3005)",
        "INSERT INTO real_acct VALUES ('C2','127 MAIN','77000',310000,5200,'N1')",
        "INSERT INTO building_res VALUES ('C2',2050,2004)",
        "INSERT INTO property_derived VALUES ('C2',3,2,'','R','Good','Avg','',2,1,1,NULL)",
        "INSERT INTO property_geo VALUES ('C2',29.7010,-95.3010)",
    ]
    if pg_url and pg_url.startswith("postgres") and get_connection:
        conn = get_connection()
        cur = conn.cursor()
        # Use execute for schema (could be multiple statements; split naive on ;) 
        for stmt in schema_sql.strip().split(';'):
            s = stmt.strip()
            if s:
                cur.execute(s)
        # Clean existing rows for idempotent reuse
        cur.execute("DELETE FROM building_res")
        cur.execute("DELETE FROM property_geo")
        cur.execute("DELETE FROM property_derived")
        cur.execute("DELETE FROM real_acct")
        for stmt in data_sql:
            cur.execute(stmt)
        conn.commit(); cur.close(); conn.close()
        return pg_url
    # Fallback: SQLite temp file
    db_path = tmp_path / "engine_test.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(schema_sql)
    for stmt in data_sql:
        cur.execute(stmt)
    conn.commit(); conn.close()
    return str(db_path)
