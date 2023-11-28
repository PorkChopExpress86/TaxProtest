import sqlite3
import os
from sqlite3 import Error
from pathlib import Path


parent_path = Path(os.path.dirname(__file__)).parent
db_path = os.path.join(parent_path, "database.sqlite")
# print(db_path)


def create_connection(db_file):
    """
    Create a database connection to a SQLite database specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)

    return conn


def create_table(conn, create_table_sql):
    """
    Create a table form the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def insert_into_building_res(conn, task):
    """
    Create a new task
    :param conn: Connection object
    :param task:
    :return:
    """

    sql = f"""INSERT INTO building_res(id, property_use_cs, bld_num, impr_tp, impr_mdl_cd, structure,structure_dscr,
                                        dpr_val, cama_replacement_cost, accrued_depr_pct, qa_cd, dscr, date_erected ,
                                        eff, yr_remodel, yr_roll, appr_by, appr_dt, notes, im_sq_ft, act_ar, heat_ar,
                                        gross_ar, eff_ar, base_ar, perimeter, pct, bld_adj, rcnld, size_index, lump_sum_adj)
                                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
            """
    cur = conn.cursor()
    cur.execute(sql, task)
    conn.commit()

    return cur.lastrowid

def main():

    parent_path = Path(os.path.dirname(__file__)).parent
    database = os.path.join(parent_path, "database.sqlite")

    sql_create_building_res_table = """CREATE TABLE IF NOT EXISTS building_res (
                                            id integer PRIMARY KEY,
                                            acct integer,
                                            property_use_cs text,
                                            bld_num integer NOT NULL,
                                            impr_tp integer,
                                            impr_mdl_cd integer,
                                            structure text,
                                            structure_dscr text,
                                            dpr_val text,
                                            cama_replacement_cost text,
                                            accrued_depr_pct numeric,
                                            qa_cd text,
                                            dscr text NOT NULL,
                                            date_erected integer,
                                            eff integer,
                                            yr_remodel integer,
                                            yr_roll text,
                                            appr_by text,
                                            appr_dt text,
                                            notes text,
                                            im_sq_ft integer NOT NULL,
                                            act_ar integer NOT NULL,
                                            heat_ar integer NOT NULL,
                                            gross_ar integer NOT NULL,
                                            eff_ar integer NOT NULL,
                                            base_ar integer NOT NULL,
                                            perimeter integer NOT NULL,
                                            pct numeric,
                                            bld_adj numeric,
                                            rcnld numeric,
                                            size_index numeric,
                                            lump_sum_adj integer
                                        );"""
    conn = create_connection(database)

    if conn is not None:

        # Create building_res table
        create_table(conn, sql_create_building_res_table)

    else:
        print("Error! cannot crate the database connection.")

    with conn:

        for row in 


if __name__ == "__main__":
    create_connection(db_path)
