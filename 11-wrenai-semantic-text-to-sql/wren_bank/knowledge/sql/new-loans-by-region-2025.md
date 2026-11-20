---
nl: How many new loans did each region open in 2025, and for how much?
sql: |
  SELECT region, COUNT(loan_origination_amount) AS new_loans, SUM(loan_origination_amount) AS loan_originations
  FROM accounts
  WHERE opened_on BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' AND product_type = 'loan'
  GROUP BY region
source: user
datasource: duckdb
---
