---
nl: What was net interest income by customer segment in 2025?
sql: |
  SELECT segment, SUM(net_interest_income) AS net_interest_income
  FROM monthly_balances
  WHERE balance_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
  GROUP BY segment
source: user
datasource: duckdb
---
