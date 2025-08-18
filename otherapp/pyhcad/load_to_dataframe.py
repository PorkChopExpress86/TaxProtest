import sqlite3

import pandas as pd
import numpy as np
import os
from zipfile import ZipFile as zf

import chardet


def load_housing_data() -> pd.DataFrame:

    if does_file_exist("hcad_data.db"):
        df = load_housing_data_from_sqlite()
    else:
        os.makedirs("Data", exist_ok=True)
        if does_file_exist("Data/complete_sample_data.csv") == False:
            with zf("housing_data.zip", "r") as zFile:
                zFile.extractall("Data")
        df = pd.read_csv("Data/complete_sample_data.csv", low_memory=False)
    return df


def load_feather_file() -> pd.DataFrame:
    if does_file_exist("house_data.feather"):
        df = pd.read_feather("house_data.feather")
    else:
        df = load_housing_data_from_sqlite()
        df.to_feather("house_data.feather")
    return df


def does_file_exist(file_path) -> bool:
    if os.path.exists(file_path):
        return True
    else:
        return False


def load_housing_data_from_sqlite() -> pd.DataFrame:
    con = sqlite3.connect("hcad_data.db")
    sql_query = """
SELECT 
	br.acct,
	br.bld_num,
	br.impr_tp,
	br.date_erected,
	br.im_sq_ft,
	ra.land_ar,
	br.perimeter,
	f.bedrooms,
	f.full_bath,
	f.half_bath,
	f.total_rooms,
	CASE
		WHEN br.dscr = 'Poor' THEN 0
		WHEN br.dscr = 'Very low' THEN 1
		WHEN br.dscr = 'Low' THEN 2
		WHEN br.dscr = 'Average' THEN 3
		WHEN br.dscr = 'Good' THEN 4
		WHEN br.dscr = 'Excellent' THEN 5
		WHEN br.dscr = 'Superior' THEN 6
	END AS dscr_e,
	IFNULL(ex1.frame_detached_garage, 0) AS frame_detached_garage,
	IFNULL(ex1.gunite_pool, 0)           AS gunite_pool,
	IFNULL(ex1.solar_panel, 0)           AS solar_panel,
	IFNULL(ex1.pool_heater, 0)           AS pool_heater,
	IFNULL(ex1.brick_garage, 0)          AS brick_garage,
	IFNULL(ex1.canopy_residential, 0)    AS canopy_residential,
	IFNULL(ex1.frame_abov, 0)            AS frame_abov,
	IFNULL(ex1.frame_shed, 0)            AS frame_shed,
	IFNULL(ex1.carport_residential, 0)   AS carport_residential,
	IFNULL(ex1.foundation_repaired, 0)   AS foundation_repaired,
	IFNULL(ex1.cracked_slab, 0)          AS cracked_slab,
	p.latitude,
	p.longitude,
	ra.land_val,
	ra.bld_val,
	br.dpr_val,
	ra.assessed_val,
	ra.mailto,
	ra.mail_addr_1,
	ra.mail_addr_2,
	ra.mail_city,
	ra.mail_state,
	ra.mail_zip
FROM building_res br
	LEFT JOIN real_acct ra ON br.acct = ra.acct
	LEFT JOIN (SELECT acct,
		IFNULL(sum(units) FILTER (WHERE type = 'RMB'), 0) AS "bedrooms",
		IFNULL(sum(units) FILTER (WHERE type = 'RMF'), 0) AS "full_bath",
		IFNULL(sum(units) FILTER (WHERE type = 'RMH'), 0) AS "half_bath",
		IFNULL(sum(units) FILTER (WHERE type = 'RMT'), 0) AS "total_rooms"
	FROM fixtures
	GROUP BY acct) f ON br.acct = f.acct
LEFT JOIN (SELECT acct,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRG1'), 0) AS frame_detached_garage,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRP5'), 0) AS gunite_pool,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RSP1'), 0) AS solar_panel,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRP9'), 0) AS pool_heater,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRG2'), 0) AS brick_garage,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRC2'), 0) AS canopy_residential,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRG3'), 0) AS frame_abov,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRS1'), 0) AS frame_shed,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RRC1'), 0) AS carport_residential,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RCS9'), 0) AS foundation_repaired,
	IFNULL(sum(asd_val) FILTER (WHERE cd = 'RCS1'), 0) AS cracked_slab
FROM extra_features_detail1
GROUP BY acct) ex1 ON br.acct = ex1.acct
LEFT JOIN parcels p ON br.acct = p.acct
WHERE br.impr_tp = 1001
      AND ra.assessed_val > 0;"""

    # Run the query on the sqlite database
    df = pd.read_sql_query(sql_query, con)

    # Drop rows that are missing data
    df.dropna(inplace=True)

    return df


def haversine(lat1, lon1, lat2, lon2) -> float:
    # Radius of Earth in miles
    r = 3958.8
    # Convert degrees to radians
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    # Haversine formula
    a = np.sin(d_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return r * c


def create_sample_data_set():
    # import housing data
    df_house = load_housing_data_from_sqlite()

    # Define the single point (latitude, longitude) to calculate the distance from
    single_point = (29.760100, -95.370100)  # Houston

    # Add a new column with distances
    df_house["distance_miles"] = df_house.apply(
        lambda row: haversine(
            single_point[0], single_point[1], row["latitude"], row["longitude"]
        ),
        axis=1,
    )

    # Remove duplicates of housing data
    df_house = (
        df_house.groupby("acct")
        .agg(
            bld_num=("bld_num", "max"),
            date_erected=("date_erected", "min"),
            im_sq_ft=("im_sq_ft", "sum"),
            land_ar=("land_ar", "mean"),
            perimeter=("perimeter", "sum"),
            bedrooms=("bedrooms", "mean"),
            full_bath=("full_bath", "mean"),
            half_bath=("half_bath", "mean"),
            total_rooms=("total_rooms", "mean"),
            dscr_e=("dscr_e", "mean"),
            frame_detached_garage=("frame_detached_garage", "mean"),
            gunite_pool=("gunite_pool", "mean"),
            pool_heater=("pool_heater", "mean"),
            solar_panel=("solar_panel", "mean"),
            brick_garage=("brick_garage", "mean"),
            canopy_residential=("canopy_residential", "mean"),
            frame_abov=("frame_abov", "mean"),
            frame_shed=("frame_shed", "mean"),
            carport_residential=("carport_residential", "mean"),
            foundation_repaired=("foundation_repaired", "mean"),
            cracked_slab=("cracked_slab", "mean"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            land_val=("land_val", "mean"),
            bld_val=("bld_val", "mean"),
            assessed_val=("assessed_val", "mean"),
        )
        .reset_index()
    )

    # assessed per square foot
    df_house["assessed_per_sqft"] = df_house["assessed_val"] / df_house["im_sq_ft"]

    # load mailing data
    df_mail = load_mail_data_from_sqlite()

    # merge data into a new dataframe
    df_merge = df_house.merge(df_mail, how="left", left_on="acct", right_on="acct")

    # Drop data with missing values
    df_merge.dropna(inplace=True)

    # Sample 10,000 rows
    df_merge.sample(n=10000, random_state=42)

    # filter for accounts in merge data in housing data and export
    h_filter = df_merge.acct.isin(df_house.acct)
    df_house = df_house[h_filter]

    # filter for accounts in merge data in mailing data and export
    m_filter = df_merge.acct.isin(df_mail.acct)
    df_mail = df_mail[m_filter]

    # export dataframes
    df_house.to_csv("sample_housing_data.csv")
    df_mail.to_csv("mailing_data.csv")


if __name__ == "__main__":
    create_sample_data_set()
