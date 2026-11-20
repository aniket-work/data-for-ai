---
nl: What was the loan book by product at the end of June 2026?
sql: |
  SELECT product_name, SUM(loan_balance) AS loan_book
  FROM monthly_balances
  WHERE balance_date = DATE '2026-06-30' AND product_type = 'loan'
  GROUP BY product_name
  ORDER BY loan_book DESC
source: user
datasource: duckdb
---
