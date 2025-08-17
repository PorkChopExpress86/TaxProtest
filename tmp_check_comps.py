import sqlite3, json
from extract_data import find_comps
conn=sqlite3.connect('data/database.sqlite');cur=conn.cursor()
cur.execute("SELECT acct FROM real_acct WHERE site_addr_1 LIKE '%WALL%' LIMIT 1")
row=cur.fetchone()
if row:
    acct=row[0]
    print('Subject acct', acct)
    res=find_comps(str(acct))
    print('Meta', json.dumps(res['meta'], indent=2))
    print('Comps count', len(res['comps']))
    print('First 5 accounts', [c['acct'] for c in res['comps'][:5]])
else:
    print('No Wall acct found')
