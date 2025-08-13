# Step 2: Extracting Data

Unzip or extract the downloaded files into the `data/` directory.

## Example (Python):
```python
import zipfile
with zipfile.ZipFile('data/export.zip', 'r') as zip_ref:
    zip_ref.extractall('data/')
```

Adjust filenames and paths as needed.
