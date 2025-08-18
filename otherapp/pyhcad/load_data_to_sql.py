import sqlite3
from venv import create
import pandas as pd
import os


def create_tables() -> None:
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect("hcad_data.db")
    cursor = conn.cursor()

    # Drop existing tables if they exist
    tables = [
        "real_acct",
        "building_res",
        "fixtures",
        "extra_features_detail1",
        "parcels",
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Dropped table {table}")

    # Recreate tables
    cursor.execute(
        """
    CREATE TABLE real_acct (
        acct TEXT PRIMARY KEY,
        yr TEXT,
        mailto TEXT,
        mail_addr_1 TEXT,
        mail_addr_2 TEXT,
        mail_city TEXT,
        mail_state TEXT,
        mail_zip TEXT,
        mail_country TEXT,
        undeliverable TEXT,
        str_pfx TEXT,
        str_num TEXT,
        str_num_sfx TEXT,
        str TEXT,
        str_sfx TEXT,
        str_sfx_dir TEXT,
        str_unit TEXT,
        site_addr_1 TEXT,
        site_addr_2 TEXT,
        site_addr_3 TEXT,
        state_class TEXT,
        school_dist TEXT,
        map_facet TEXT,
        key_map TEXT,
        Neighborhood_Code TEXT,
        Neighborhood_Grp TEXT,
        Market_Area_1 TEXT,
        Market_Area_1_Dscr TEXT,
        Market_Area_2 TEXT,
        Market_Area_2_Dscr TEXT,
        econ_area TEXT,
        econ_bld_class TEXT,
        center_code TEXT,
        yr_impr TEXT,
        yr_annexed TEXT,
        splt_dt TEXT,
        dsc_cd TEXT,
        nxt_bld TEXT,
        bld_ar TEXT,
        land_ar TEXT,
        acreage TEXT,
        Cap_acct TEXT,
        shared_cad TEXT,
        land_val TEXT,
        bld_val TEXT,
        x_features_val TEXT,
        ag_val TEXT,
        assessed_val TEXT,
        tot_appr_val TEXT,
        tot_mkt_val TEXT,
        prior_land_val TEXT,
        prior_bld_val TEXT,
        prior_x_features_val TEXT,
        prior_ag_val TEXT,
        prior_tot_appr_val TEXT,
        prior_tot_mkt_val TEXT,
        new_construction_val TEXT,
        tot_rcn_val TEXT,
        value_status TEXT,
        noticed TEXT,
        notice_dt TEXT,
        protested TEXT,
        certified_date TEXT,
        rev_dt TEXT,
        rev_by TEXT,
        new_own_dt TEXT,
        lgl_1 TEXT,
        lgl_2 TEXT,
        lgl_3 TEXT,
        lgl_4 TEXT,
        jurs TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE building_res (
        acct TEXT NOT NULL,
        bld_num TEXT NOT NULL,
        property_use_cd TEXT,
        impr_tp TEXT,
        impr_mdl_cd TEXT,
        structure TEXT,
        structure_dscr TEXT,
        dpr_val TEXT,
        cama_replacement_cost TEXT,
        accrued_depr_pct TEXT,
        qa_cd TEXT,
        dscr TEXT,
        date_erected TEXT,
        eff TEXT,
        yr_remodel TEXT,
        yr_roll TEXT,
        appr_by TEXT,
        appr_dt TEXT,
        notes TEXT,
        im_sq_ft TEXT,
        act_ar TEXT,
        heat_ar TEXT,
        gross_ar TEXT,
        eff_ar TEXT,
        base_ar TEXT,
        perimeter TEXT,
        pct TEXT,
        bld_adj TEXT,
        rcnld TEXT,
        size_index TEXT,
        lump_sum_adj TEXT,
        PRIMARY KEY (acct, bld_num),
        FOREIGN KEY (acct) REFERENCES real_acct(acct)
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE fixtures (
        acct TEXT NOT NULL,
        bld_num TEXT NOT NULL,
        type TEXT NOT NULL,
        type_dscr TEXT,
        units TEXT,
        PRIMARY KEY (acct, bld_num, type),
        FOREIGN KEY (acct) REFERENCES real_acct(acct)
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE extra_features_detail1 (
        acct TEXT NOT NULL,
        cd TEXT,
        dscr TEXT,
        grade TEXT,
        cond_cd TEXT,
        bld_num TEXT,
        length TEXT,
        width TEXT,
        units TEXT,
        unit_price TEXT,
        adj_unit_price TEXT,
        pct_comp TEXT,
        act_yr TEXT,
        eff_yr TEXT,
        roll_yr TEXT,
        DT TEXT,
        pct_cond TEXT,
        dpr_val TEXT,
        note TEXT,
        asd_val TEXT,
        PRIMARY KEY (acct, cd),
        FOREIGN KEY (acct) REFERENCES real_acct(acct)
    )
    """
    )

    # Create a new table for parcels
    cursor.execute(
        """
    CREATE TABLE parcels (
        acct TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        PRIMARY KEY (acct),
        FOREIGN KEY (acct) REFERENCES real_acct(acct)
    )
    """
    )

    conn.commit()
    print("Tables recreated successfully.")

    # Close the connection
    conn.close()


# Function to import data from text files
def import_data(file_name, table_name, delimiter="\t") -> None:

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect("hcad_data.db")
    cursor = conn.cursor()

    file_path = os.path.join(
        "Data", file_name
    )  # Assumes text files are in a 'Data' folder
    if os.path.exists(file_path):
        print(f"Importing data from {file_name} into {table_name}...")

        try:
            # Read the text file into a DataFrame using a broader encoding
            df = pd.read_csv(
                file_path,
                delimiter=delimiter,
                dtype=str,
                encoding="ISO-8859-1",
                on_bad_lines="warn",
            )
        except UnicodeDecodeError:
            print(f"Encoding error in {file_name}. Trying Latin-1 encoding.")
            df = pd.read_csv(
                file_path, delimiter=delimiter, dtype=str, encoding="latin-1"
            )

        # Trim trailing and leading spaces from all string columns
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Explicitly trim `acct` fields in affected tables
        if "acct" in df.columns:
            df["acct"] = df["acct"].str.strip()

        # Remove duplicates for tables with composite primary keys
        if table_name == "fixtures":
            df.drop_duplicates(
                subset=["acct", "bld_num", "type"], keep="first", inplace=True
            )
        elif table_name == "extra_features_detail1":
            df.drop_duplicates(subset=["acct", "cd"], keep="first", inplace=True)

        # Insert data into SQLite
        df.to_sql(table_name, conn, if_exists="append", index=False)
        print(f"Successfully imported {len(df)} records into {table_name}.")
    else:
        print(f"File {file_name} not found. Skipping.")

    # Close the connection
    conn.close()


# Function to import parcels.csv
def import_parcels() -> None:
    file_path = os.path.join(
        "Data", "parcels.csv"
    )  # Assumes parcels.csv is in the 'Data' folder
    if os.path.exists(file_path):
        print(f"Importing data from parcels.csv into parcels table...")

        try:
            df = pd.read_csv(
                file_path,
                dtype={"HCAD_NUM": str, "latitude": float, "longitude": float},
                encoding="ISO-8859-1",
            )
        except UnicodeDecodeError:
            print(f"Encoding error in parcels.csv. Trying Latin-1 encoding.")
            df = pd.read_csv(
                file_path,
                dtype={"HCAD_NUM": str, "latitude": float, "longitude": float},
                encoding="latin-1",
            )

        # Trim trailing and leading spaces from all string columns
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Select only the required columns
        df = df[["HCAD_NUM", "latitude", "longitude"]].rename(
            columns={"HCAD_NUM": "acct"}
        )

        # Drop duplicate accounts if needed
        df.drop_duplicates(subset=["acct"], keep="first", inplace=True)

        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect("hcad_data.db")
        cursor = conn.cursor()

        # Insert into SQLite
        df.to_sql("parcels", conn, if_exists="append", index=False)
        print(f"Successfully imported {len(df)} records into parcels.")
    else:
        print(f"File parcels.csv not found. Skipping.")

    # Close the connection
    conn.close()


if __name__ == "__main__":

    create_tables()

    # Import data for each table
    import_data("real_acct.txt", "real_acct")
    import_data("building_res.txt", "building_res")
    import_data("fixtures.txt", "fixtures")
    import_data("extra_features_detail1.txt", "extra_features_detail1")

    # Import GIS parcel data
    import_parcels()

    print("All data imported successfully.")
