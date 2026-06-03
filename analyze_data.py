import sqlite3
import pandas as pd

conn = sqlite3.connect(r'C:\Users\11029\Desktop\chatbi-agent\northwind.db')

print("=" * 50)
print("1. 月度销售额分布")
df = pd.read_sql_query("""
SELECT strftime('%Y-%m', o.OrderDate) as month,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales,
       COUNT(DISTINCT o.OrderID) as orders
FROM Orders o JOIN [Order Details] od ON o.OrderID = od.OrderID
GROUP BY month ORDER BY month
""", conn)
print(df.to_string())
print(f"\n月销售额 均值:{df.sales.mean():.0f} 最小:{df.sales.min():.0f} 最大:{df.sales.max():.0f}")
print(f"月订单量 均值:{df.orders.mean():.0f} 最小:{df.orders.min():.0f} 最大:{df.orders.max():.0f}")

print("\n" + "=" * 50)
print("2. 各产品类别销售额")
df2 = pd.read_sql_query("""
SELECT c.CategoryName,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales,
       COUNT(DISTINCT o.OrderID) as orders,
       ROUND(AVG(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as avg_order_value
FROM [Order Details] od
JOIN Orders o ON o.OrderID = od.OrderID
JOIN Products p ON p.ProductID = od.ProductID
JOIN Categories c ON c.CategoryID = p.CategoryID
GROUP BY c.CategoryName ORDER BY sales DESC
""", conn)
print(df2.to_string())

print("\n" + "=" * 50)
print("3. 各国销售额 Top10")
df3 = pd.read_sql_query("""
SELECT o.ShipCountry,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales,
       COUNT(DISTINCT o.OrderID) as orders,
       COUNT(DISTINCT o.CustomerID) as customers
FROM Orders o JOIN [Order Details] od ON o.OrderID = od.OrderID
GROUP BY o.ShipCountry ORDER BY sales DESC LIMIT 10
""", conn)
print(df3.to_string())

print("\n" + "=" * 50)
print("4. 产品销售额分布（Top10 vs 其余）")
df4 = pd.read_sql_query("""
SELECT p.ProductName, c.CategoryName,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales,
       SUM(od.Quantity) as qty,
       ROUND(AVG(od.Discount)*100, 1) as avg_discount_pct
FROM [Order Details] od
JOIN Products p ON p.ProductID = od.ProductID
JOIN Categories c ON c.CategoryID = p.CategoryID
GROUP BY p.ProductID ORDER BY sales DESC LIMIT 15
""", conn)
print(df4.to_string())

print("\n" + "=" * 50)
print("5. 员工业绩")
df5 = pd.read_sql_query("""
SELECT e.FirstName || ' ' || e.LastName as employee,
       COUNT(DISTINCT o.OrderID) as orders,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales
FROM Orders o
JOIN Employees e ON e.EmployeeID = o.EmployeeID
JOIN [Order Details] od ON od.OrderID = o.OrderID
GROUP BY e.EmployeeID ORDER BY sales DESC
""", conn)
print(df5.to_string())

print("\n" + "=" * 50)
print("6. 季度销售规律")
df6 = pd.read_sql_query("""
SELECT strftime('%Y', o.OrderDate) as year,
       CASE WHEN strftime('%m', o.OrderDate) IN ('01','02','03') THEN 'Q1'
            WHEN strftime('%m', o.OrderDate) IN ('04','05','06') THEN 'Q2'
            WHEN strftime('%m', o.OrderDate) IN ('07','08','09') THEN 'Q3'
            ELSE 'Q4' END as quarter,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1-od.Discount)), 2) as sales
FROM Orders o JOIN [Order Details] od ON o.OrderID = od.OrderID
GROUP BY year, quarter ORDER BY year, quarter
""", conn)
print(df6.to_string())

conn.close()
