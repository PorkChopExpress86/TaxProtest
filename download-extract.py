"""
This file will be called by a timming function by the os like cron and will download
the data on a schedule.
"""
import wget
import os
import glob
from zipfile import ZipFile as zf
from datetime import datetime
from pathlib import Path

parent_path = Path(os.path.dirname(__file__)).parent
zip_data_path = os.path.join(parent_path, "zipped_data")
text_data_path = os.path.join(parent_path, "text-files")


def download_zip(year=datetime.now().strftime("%Y")):
    """
    Removes files from a directory and downloads the zip files needed
    :param: year: The year of the files to be download
    """
    # remove files from Downloaded Data
    files = glob.glob(zip_data_path + "/*.zip")
    for file in files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {file} : {e.strerror}")

    # Download files
    # wget.download(
    #     url=("https://download.hcad.org/data/CAMA/" + year + "/Real_building_land.zip"),
    #     out=os.path.join(zip_data_path, "Real_building_land.zip"),
    # )
    owners_file_path = "zipped-data/Real_acct_owner.zip"  # os.path.join(zip_data_path, "Real_acct_owner.zip")
    link = "https://download.hcad.org/data/CAMA/" + year + "/Real_acct_owner.zip"
    wget.download(link, owners_file_path)


def unzip_file(file, dest):
    """
    Unzip a *.zip file to the destination directory

    Parameters
    file= string of file path, ex. 'Download.zip'
    dest= string of directory path, ex. 'Data/'

    """
    file_list = ["building_res.txt", "real_acct.txt"]

    with zf(file, "r") as zip_obj:
        list_of_file_names = zip_obj.namelist()

        for file_name in list_of_file_names:
            if file_name in file_list:
                zip_obj.extract(file_name, dest)


if __name__ == "__main__":
    print("Downloading data...")
    # Download files
    download_zip()

    # print("Extracting data...")
    # Extract files
    # unzip_file("zipped-data/Real_building_land.zip", "text-files/")
    # unzip_file(os.path.join(zip_data_path, "Real_acct_owners.zip"), text_data_path)
