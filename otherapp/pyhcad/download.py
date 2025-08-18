import os
import time
from operator import truediv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def wait_for_download_completion(download_dir, timeout=360, poll_interval=1):
    """
    Waits for the download to complete by checking the download directory.

    Parameters:
        download_dir (str): Directory where files are being downloaded.
        timeout (int): Maximum time to wait for the download, in seconds.
        poll_interval (int): Interval in seconds to check the directory.

    Returns:
        bool: True if the download completes within the timeout, False otherwise.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for files still downloading (e.g., with .crdownload or .part extensions)
        if not any(
            file_name.endswith((".crdownload", ".part", ".tmp"))
            for file_name in os.listdir(download_dir)
        ):
            return True
        time.sleep(poll_interval)
    return False


def download_link_by_url(url, target_urls, download_dir=None, wait_time=10):
    """
    Downloads a file by clicking a link with a specific URL on an AJAX website.

    Parameters:
        url (str): The URL of the website.
        target_urls (list): The exact URL of the link to find and click.
        download_dir (str): the directory to save the downloaded files.
        wait_time (int): Maximum time to wait for the link to appear, in seconds.
    """
    # Set default download directory to a "downloads" folder in the script's directory
    if download_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(script_dir, "downloads")

    # Set up Chrome options for downloads
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless')  # Run Chrome in headless mode
    # chrome_options.add_argument('--disable-gpu')  # Optional: Disable GPU acceleration for headless mode

    prefs = {
        "download.default_directory": os.path.abspath(download_dir)
    }  # Change to your desired download path
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialize WebDriver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    try:
        # Ensure the download directory exists
        os.makedirs(download_dir, exist_ok=True)

        # Open the website
        driver.get(url)

        for url in target_urls:

            filename = url.split("/")[-1]

            # Remove the existing file if it exists
            target_file = os.path.join(download_dir, filename)
            if os.path.exists(target_file):
                print(f"File {filename} already exists. Overwriting it.")
                os.remove(target_file)

            success = False
            for attempt in range(2):
                try:
                    # Wait for the link with the target URL to appear
                    link_element = WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located(
                            (By.XPATH, f"//a[@href='{url}']")
                        )
                    )

                    # Click the link
                    link_element.click()

                    time.sleep(5)

                    # Wait for the download to complete
                    if wait_for_download_completion(download_dir):
                        print("Download completed successfully!")
                        success = True
                        break
                except Exception as e:
                    print(f"Attempt {attempt + 1} for {filename} failed: {e}")
                    if attempt < 1:
                        print("Retrying download...")
            if not success:
                print(
                    f"Failed to download {filename} after 2 attempts. Please do so manually.!"
                )
    finally:
        # Close the browser
        driver.quit()


if __name__ == "__main__":
    file_urls = [
        "https://download.hcad.org/data/CAMA/2024/Real_acct_owner.zip",
        "https://download.hcad.org/data/CAMA/2024/Real_building_land.zip",
        "https://download.hcad.org/data/CAMA/2024/Code_description_real.zip",
    ]

    # Download all three zips
    ajax_site_url = "https://hcad.org/pdata/pdata-property-downloads.html"  # Replace with the target website's URL
    download_link_by_url(ajax_site_url, file_urls, "Zips", 90)

    # Download GIS data on tax particles
    file_urls = ["https://download.hcad.org/data/GIS/Parcels.zip"]
    ajax_site_url = "https://hcad.org/pdata/pdata-gis-downloads.html"
    download_link_by_url(ajax_site_url, file_urls, "Zips", 90)
