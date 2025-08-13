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

# Ensure required directories exist
os.makedirs(zip_data_path, exist_ok=True)
os.makedirs(text_data_path, exist_ok=True)


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

    url_list = [
        f"https://download.hcad.org/data/CAMA/{year}/Real_building_land.zip",
        f"https://download.hcad.org/data/CAMA/{year}/Real_acct_owner.zip",
        f"https://download.hcad.org/data/CAMA/{year}/Hearing_files.zip",
        f"https://download.hcad.org/data/CAMA/{year}/Code_description_real.zip",
        f"https://download.hcad.org/data/CAMA/{year}/PP_files.zip",
        f"https://download.hcad.org/data/CAMA/{year}/Code_description_pp.zip",
        "https://download.hcad.org/data/GIS/GIS_Public.zip"
    ]

    output_list = [
        f"{zip_data_path}/Real_building_land.zip",
        f"{zip_data_path}/Real_acct_owner.zip",
        f"{zip_data_path}/Hearing_files.zip",
        f"{zip_data_path}/Code_description_real.zip",
        f"{zip_data_path}/PP_files.zip",
        f"{zip_data_path}/Code_description_pp.zip",
        f"{zip_data_path}/GIS_Public.zip"
    ]

    # Download both files with certificate verification enabled
    for url, output_path in zip(url_list, output_list):
        try:
            resp = requests.get(url, allow_redirects=True)  # Default: verify=True
            resp.raise_for_status()
            with open(output_path, 'wb') as file:
                file.write(resp.content)
        except requests.exceptions.SSLError as ssl_err:
            print(f"SSL error while downloading {url}: {ssl_err}")
        except requests.exceptions.RequestException as req_err:
            print(f"Request error while downloading {url}: {req_err}")


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
    file_list = [
        "building_res.txt",
    "land.txt",
        "real_acct.txt",
        "Hearing_files.txt",
        "Code_description_real.txt",
        "PP_files.txt",
        "Code_description_pp.txt",
        # GIS files may have different extensions, so extract all files if it's GIS_Public.zip
    ]

    # Ensure destination directory exists
    os.makedirs(dest, exist_ok=True)

    with zf(file, "r") as zip_obj:
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
    unzip_files(os.path.join(zip_data_path, "Real_building_land.zip"), text_data_path)
    unzip_files(os.path.join(zip_data_path, "Real_acct_owner.zip"), text_data_path)
    unzip_files(os.path.join(zip_data_path, "Hearing_files.zip"), text_data_path)
    unzip_files(os.path.join(zip_data_path, "Code_description_real.zip"), text_data_path)
    unzip_files(os.path.join(zip_data_path, "PP_files.zip"), text_data_path)
    unzip_files(os.path.join(zip_data_path, "Code_description_pp.zip"), text_data_path)
    # For GIS_Public.zip, extract all files (not just .txt)
    gis_zip = os.path.join(zip_data_path, "GIS_Public.zip")
    if os.path.exists(gis_zip):
        with zf(gis_zip, "r") as zip_obj:
            zip_obj.extractall(text_data_path)
