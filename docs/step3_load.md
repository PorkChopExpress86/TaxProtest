# Step 3: Loading Data into SQLite

Load the extracted data files into a SQLite database. Use the codebook (pdataCodebook.pdf) to define the schema.

## Example (Python):
```python
import sqlite3
import pandas as pd
conn = sqlite3.connect('pdata.db')
df = pd.read_csv('data/your_data.csv')
df.to_sql('property', conn, if_exists='replace', index=False)
conn.close()
```

Adjust table and column names as needed.
