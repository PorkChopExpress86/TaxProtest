import os
import sqlite3
from zipfile import ZipFile as zf

import chardet
import pandas as pd


def unzip_files(src, dst, file_list):
    for root, dirs, files in os.walk(src):
        for name in files:
            # file_name = name.split('.')[0]
            file_type = name.split(".")[-1]
            if file_type == "zip":
                file = str(os.path.join(root, name))

                with zf(file, "r") as zFile:
                    all_files = zFile.namelist()
                    files_to_unzip = [f for f in all_files if f in file_list]

                    if not files_to_unzip:
                        print(f"No files in {file}")

                    for file in files_to_unzip:
                        print(f"Unzipping {file}")
                        zFile.extract(file, f"{dst}/")


def load_tables_to_sqlite(file_list):
    encoder_dict = {
        "building_res.txt": "Windows - 1252",
        "exterior.txt": "ascii",
        "extra_features.txt": "ascii",
        "fixtures.txt": "ascii",
        "land.txt": "ascii",
        "real_neighborhood_code.txt": "ascii",
        "real_acct.txt": "Windows - 1252",
        "parcels.csv": "utf-8",
        "extra_features_detail1.txt": "utf-8",
        "kaggle_dataset.csv": "utf-8",
    }

    conn = sqlite3.connect("HouseProtestValues.db")
    cursor = conn.cursor()

    for file in file_list:
        encoder = encoder_dict[file]

        try:
            print(f"Reading {file} into dataframe...")
            if file == "parcels.csv":
                # Exception for the parcel file exported from QGIS
                df = pd.read_csv(f"Data/{file}", low_memory=False)
                df = df[["HCAD_NUM", "latitude", "longitude"]]
            else:
                df = pd.read_csv(
                    f"Data/{file}", sep="\t", encoding=encoder, low_memory=False
                )

            # Strip extra spaces on all object column types
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

        except Exception as e:
            print(f"{file} was not read by pandas. See exception:\n {e}")

        table_name = file.split(".")[0]
        if df is not None:
            print(f"\tWriting {file} to sqlite db...")
            df.to_sql(table_name, conn, if_exists="replace", index=True)

    conn.commit()
    conn.close()


def detect_encoding():
    """
    loops through all the txt files in data and detects encoding
    :return:
    """
    for root, dirs, files in os.walk("Data"):
        for file in files:
            file_path = os.path.join(root, file)
            print(file)
            with open(file_path, "rb") as f:
                result = chardet.detect(f.read())
                print(f"{file}: {result['encoding']}")


if __name__ == "__main__":
    print("Extracting data...")
    data_files = [
        "real_neighborhood_code.txt",
        "building_res.txt",
        "real_acct.txt",
        "land.txt",
        "fixtures.txt",
        "extra_features.txt",
        "exterior.txt",
        "extra_features_detail1.txt",
    ]

    # Extract files
    unzip_files(src="Zips", dst="Data", file_list=data_files)

    # # Add parcels.csv
    data_files.append("parcels.csv")

    # # Load tables into sqlite data
    load_tables_to_sqlite(data_files)

    print("Done!")
