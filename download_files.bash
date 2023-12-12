#!/bin/bash

rm -rf zipped_data
mkdir zipped_data

# Download Real_building_land.zip file
curl --tlsv1.1 --insecure https://download.hcad.org/data/CAMA/2023/Real_building_land.zip --output ./zipped_data/Real_building_land.zip

# Download Real_acct_owner.zip file
curl --tlsv1.1 --insecure https://download.hcad.org/data/CAMA/2023/Real_acct_owner.zip --output ./zipped_data/Real_acct_owner.zip

# Unzip files
rm -rf ./text_files
mkdir text_files

unzip -o zipped_data/Real_acct_owner.zip "real_acct.txt" -d text_files

unzip -o zipped_data/Real_building_land.zip "building_res.txt" -d text_files


# Run command to create the database files and tables
python insert_data.py

mkdir Exports