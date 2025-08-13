# Step 1: Downloading Data

Use the provided script or instructions to download the property database export files from the official source (URL or FTP).

- Save files to the `data/` directory.
- Example script: `download_extract.py` or `download_files.bash`

## Example (Python):
```python
import requests
url = 'YOUR_DATA_SOURCE_URL'
response = requests.get(url)
with open('data/export.zip', 'wb') as f:
    f.write(response.content)
```

Replace `YOUR_DATA_SOURCE_URL` with the actual URL.
