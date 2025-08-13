import os
import sqlite3


def strip_list(l):
    return [x.strip() for x in l]


def insert_data(text_file_path, table_name, num_of_cols, cur):
    """
    Reads a text file line by line and inserts each lin into a database.

    Parameters
    text_file_path [string] = the path to the text file that has all the data
    table_name [string] = the name of the table the data will be inserted into
    num_of_cols [integer] = the number of columns that will be inserted
    cur [cursor] = sqlite3 connection. cursor object
    """
    inserts = "?," * num_of_cols
    inserts = inserts[:-1]
    line_num = 0
    with open(text_file_path, 'rb') as f:
        for line in f:
            # Some files are not uft-8 and need to be decoded
            line = line.decode(errors='replace')
            line_list = line.split("\t")
            line_list = tuple(strip_list(line_list))
            line_len = len(line_list)
            if line_num != 0 and line_len == num_of_cols:
                cur.executemany(f"INSERT INTO {table_name} VALUES ({inserts})", (line_list,))
            else:
                print(f"{table_name} line number {line_num} has {len(line_list)} elements!")
                line_num += 1


def load_data():
    try:
        con = sqlite3.connect("database.sqlite")

        cur = con.cursor()

        print("\tSuccessfully connected to SQLite")

        cur.execute("DROP TABLE IF EXISTS building_res;")

        cur.execute("""CREATE TABLE IF NOT EXISTS building_res (
                                                acct INTEGER,
                                                property_use_cs TEXT,
                                                bld_num INTEGER NOT NULL,
                                                impr_tp INTEGER,
                                                impr_mdl_cd INTEGER,
                                                structure TEXT,
                                                structure_dscr TEXT,
                                                dpr_val TEXT,
                                                cama_replacement_cost TEXT,
                                                accrued_depr_pct NUMERIC,
                                                qa_cd TEXT,
                                                dscr TEXT NOT NULL,
                                                date_erected INTEGER,
                                                eff INTEGER,
                                                yr_remodel INTEGER,
                                                yr_roll TEXT,
                                                appr_by TEXT,
                                                appr_dt TEXT,
                                                notes TEXT,
                                                im_sq_ft INTEGER NOT NULL,
                                                act_ar INTEGER NOT NULL,
                                                heat_ar INTEGER NOT NULL,
                                                gross_ar INTEGER NOT NULL,
                                                eff_ar INTEGER NOT NULL,
                                                base_ar INTEGER NOT NULL,
                                                perimeter INTEGER NOT NULL,
                                                pct NUMERIC,
                                                bld_adj NUMERIC,
                                                rcnld NUMERIC,
                                                size_index NUMERIC,
                                                lump_sum_adj INTEGER,
                                                FOREIGN KEY (acct) REFERENCES real_acct(acct));""")
        cur.execute("DROP TABLE IF EXISTS real_acct;")
        cur.execute("""CREATE TABLE IF NOT EXISTS real_acct(
                        acct INTEGER PRIMARY KEY,
                        yr INTEGER,
                        mailto TEXT,
                        mail_addr_1 TEXT,
                        mail_addr_2 TEXT,
                        mail_city TEXT,
                        mail_state TEXT,	
                        mail_zip  TEXT,
                        mail_country TEXT,
                        undeliverable TEXT,
                        str_pfx  TEXT,
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
                        acreage  TEXT,	
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
                        jurs TEXT);""")

        # relative filepaths
        dirname = os.path.dirname(__file__)

        con.commit()
        print("\tSuccessfully created tables")

        print("\tInserting building res data...")
        insert_data(os.path.join(dirname, "text_files/building_res.txt"), "building_res", 31, cur)

        print("\tInserting real_acct data...")
        insert_data(os.path.join(dirname, "text_files/real_acct.txt"), "real_acct", 71, cur)

        con.commit()

        cur.close()

    except sqlite3.Error as error:
        print("Failed to insert data into sqlite table", error)

    finally:
        if con:
            con.commit()
            con.close()
            print("\tThe SQLite connection is closed")


if __name__ == "__main__":
    load_data()
