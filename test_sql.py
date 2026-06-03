import sqlite3, pandas as pd
conn = sqlite3.connect(r'C:\Users\11029\Desktop\chatbi-agent\northwind.db')

# 看OrderDate实际存的格式
df = pd.read_sql_query("SELECT OrderDate FROM Orders LIMIT 5", conn)
print("OrderDate样例:", df['OrderDate'].tolist())

# 试试直接用LIKE过滤
df2 = pd.read_sql_query("SELECT OrderDate FROM Orders WHERE OrderDate LIKE '1997%' LIMIT 3", conn)
print("1997年数据:", df2['OrderDate'].tolist())
conn.close()
