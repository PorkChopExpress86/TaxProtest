```prompt
Create a Flask-based property lookup tool with the following workflow:

1. Download the property database export files from the official source (URL or FTP). Save them to a local directory.
2. Unzip or extract the downloaded files into a working directory.
3. Load the extracted data into a SQLite database. Use the provided codebook (pdataCodebook.pdf) to define the schema and map the data fields.
4. Build a Flask web frontend that allows users to:
	- Enter their name or address to search for their property information.
	- View the search results in a table.
	- Export the search results to an Excel file and download it.
5. After the Excel file is downloaded, automatically delete it from the server.

Requirements:
- Use Python for all scripting and backend logic.
- Use pandas or openpyxl for Excel export.
- Ensure the web interface is user-friendly and secure.
- Provide clear instructions or scripts for each step (downloading, extraction, loading, running the Flask app).
```
