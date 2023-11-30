"""
This file will be called by a timing function by the os like cron and will download
the data on a schedule.
"""
import glob
import os
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile as zf

import requests

parent_path = Path(os.path.dirname(__file__))
zip_data_path = os.path.join(parent_path, "zipped_data")
text_data_path = os.path.join(parent_path, "text_files")


def remove_zipped_files():
    # remove files from Downloaded Data
    files = glob.glob(zip_data_path + "/*.zip")
    for file in files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {file} : {e.strerror}")


def pycurl_download():
    year = datetime.now().strftime("%Y")

    url_list = [f"https://download.hcad.org/data/CAMA/{year}/Real_building_land.zip",
                f"https://download.hcad.org/data/CAMA/{year}/Real_acct_owner.zip"]

    output_list = [f"{zip_data_path}/Real_building_land.zip", f"{zip_data_path}/Real_acct_owner.zip"]

    response = requests.get(url_list[0], allow_redirects=True, verify=False)

    with open("zipped_data/Real_acct_owner.zip", 'wb') as file:
        file.write(response)


def download_zip(year=datetime.now().strftime("%Y")):
    """
    Removes files from a directory and downloads the zip files needed
    :param: year: The year of the files to be downloaded
    """

    file_list = ["Real_acct_owner.zip", "Real_building_land.zip"]
    # https://download.hcad.org/data/CAMA/2023/Real_building_land.zip

    url_list = [f"https://download.hcad.org/data/CAMA/{year}/Real_building_land.zip",
                f"https://download.hcad.org/data/CAMA/{year}/Real_acct_owner.zip"]

    output_list = [f"{zip_data_path}/Real_building_land.zip", f"{zip_data_path}/Real_acct_owner.zip"]

    # for file_name in file_list:  # os.system(f"curl --tlsv1.1 {url_list[0]} --output {output_list[0]}")  # os.system(f"curl --tlsv1.1 {url_list[1]} --output {output_list[1]}")  # acct_owner = os.system(f"curl --tlsv1.1 {url_list[0]}").read()


def unzip_files(file, dest):
    """
    Unzip a *.zip file to the destination directory

    Parameters
    file= string of file path, ex. 'Download.zip'
    dest= string of directory path, ex. 'Data/'

    """
    file_list = ["building_res.txt", "real_acct.txt"]

    with zf(file, "w") as zip_obj:
        list_of_file_names = zip_obj.namelist()

        for file_name in list_of_file_names:
            if file_name in file_list:
                zip_obj.extract(file_name, dest)


if __name__ == "__main__":
    print("Downloading data...")
    # Download files
    # download_zip()
    pycurl_download()

    print("Extracting data...")
    # Extract files
    unzip_files(os.path.join(zip_data_path, "Real_building_land.zip"), os.path.join(text_data_path, "real_acct.txt"))
    unzip_files(os.path.join(zip_data_path, "Real_acct_owner.zip"), os.path.join(text_data_path, "building_res.txt"))
