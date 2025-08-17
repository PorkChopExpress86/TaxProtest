import sqlite3, re, json, os, sys
DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'database.sqlite')
DB = os.path.abspath(DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('PRAGMA table_info(real_acct)')
cols = [r[1] for r in cur.fetchall()]
class_cols = [c for c in cols if re.search(r'(state.*class|state_class|class$|use_cd|property_use)', c, re.I)]
# Fallback: any with 'class' or 'state'
if not class_cols:
    class_cols = [c for c in cols if re.search(r'(class|state|use)', c, re.I)]
result = {}
for col in class_cols:
    try:
        cur.execute(f"SELECT {col}, COUNT(*) FROM real_acct GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 25")
        result[col] = cur.fetchall()
    except Exception as e:
        result[col] = [('ERR', str(e))]
print(json.dumps({'db': DB, 'candidate_columns': class_cols, 'samples': result}, indent=2))
conn.close()
