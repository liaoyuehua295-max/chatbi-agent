import sqlite3
conn = sqlite3.connect(r'C:\Users\11029\Desktop\chatbi-agent\shuidi.db')
for table in ['hospitals', 'diseases', 'campaigns', 'donations', 'withdrawals']:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    sample = conn.execute(f'SELECT * FROM {table} LIMIT 2').fetchall()
    print(f'{table}: {count} rows')
    for row in sample:
        print(' ', row)
    print()
conn.close()
