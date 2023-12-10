import os

import pandas as pd
from sqlalchemy import create_engine

basedir = os.path.abspath(os.path.dirname(__file__))

# Create engine to connect with DB
try:
    engine = create_engine('sqlite:///' + os.path.join(basedir, 'database.sqlite'))
except:
    print("Can't create engine")


def load_data_to_sqlite():
    # read residential data to dataframe
    res = pd.read_csv(r'Data/building_res.txt', delimiter='\t', encoding='mbcs')

    # read land data to dataframe
    land = pd.read_csv(r'Data/land.txt', delimiter='\t', encoding='utf-8')

    # read owners data to dataframe
    real_acct = pd.read_csv(r'Data/real_acct.txt', delimiter='\t', encoding='mbcs')

    with engine.begin() as connection:
        # Insert data for buildingres table
        res.to_sql('building_res', con=connection, if_exists='replace')
        print('buildingres table updated...')

        # Insert data for lands
        land.to_sql('land', con=connection, if_exists='replace')
        print('lands table updated...')

        # insert data for owners
        real_acct.to_sql('real_acct', con=connection, if_exists='replace')
        print('owners table updated...')
        print('Done, ok!')


def extract_excel_file(account="", street="", zip_code=""):
    empty_str = ""
    sql = """
    SELECT ra.site_addr_1 AS 'Address',
        ra.site_addr_3 AS 'Zip Code',
        br.eff AS 'Build Year',
        ra.land_val AS 'Land Value',
        ra.bld_val AS 'Building Value',
        CAST(ra.acct AS TEXT) AS 'Account Number',
        ra.tot_mkt_val AS 'Market Value',
        br.im_sq_ft AS 'Building Area',
        (ra.tot_mkt_val / br.im_sq_ft) AS 'Price Per Sq Ft',
        ra.land_ar AS 'Land Area'
    FROM real_acct AS ra
    JOIN building_res AS br ON ra.acct = br.acct
    WHERE """

    file_name = ''
    if account is not empty_str:
        sql += "ra.acct LIKE '%" + account + "%' AND "
        file_name += account + ' '
    if street is not empty_str:
        sql += "ra.site_addr_1 LIKE '%" + street + "%' AND "
        file_name += street + ' '
    if zip_code is not empty_str:
        sql += "ra.site_addr_3 LIKE '%" + zip_code + "%' AND "
        file_name += zip_code + ' '

    # Add closing colon
    sql = sql[:-5] + ';'

    # Fix filename
    file_name += 'Home Info.xlsx'

    # Start connection with sqlite database
    with engine.begin() as connection:
        df = pd.read_sql(sql, con=connection)
        df.to_excel('Exports/' + file_name, sheet_name='Info', engine='openpyxl')
        return file_name
