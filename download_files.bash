#!/usr/bin/env bash

# Download Real_building_land.zip file
curl --tlsv1.1 https://download.hcad.org/data/CAMA/2023/Real_building_land.zip --output ./zipped_data/Real_building_land.zip

# Download Real_acct_owner.zip file
curl --tlsv1.1 https://download.hcad.org/data/CAMA/2023/Real_acct_owner.zip --output ./zipped_data/Real_acct_owner.zip

# Unzip files
unzip -o zipped_data/Real_acct_owner.zip "real_acct.txt" -d text_files

unzip -o zipped_data/Real_building_land.zip "building_res.txt" -d text_files


# Run command to create the database files and tables
python3.12 insert_data.py

sqlite3 -separator ',' stuff.db ".import myfile.csv t_table_name"
