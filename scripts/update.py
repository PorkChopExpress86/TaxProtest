from insert_data import load_data
from download_extract import download_zip, unzip_files

import os
from pathlib import Path

parent_path = Path(os.path.dirname(__file__)).parent
zip_data_path = os.path.join(parent_path, "TaxProtest/zipped_data")
text_data_path = os.path.join(parent_path, "TaxProtest/text_files")


if __name__ == '__main__':
    print("Downloading files...")
    # download_zip('2023')

    print("Unzipping files...")
    # unzip_files(os.path.join(zip_data_path, "Real_building_land.zip"), text_data_path)
    # unzip_files(os.path.join(zip_data_path, "Real_acct_owner.zip"), text_data_path)

    print("Loading data in to database...")
    load_data()

    print("Done!")