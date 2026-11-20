-- Finance team: "Total deposits, 2026" (copied from an old year-end report)
-- Drift: sums EVERY month-end snapshot, so each dollar is counted up to ten times.
SELECT SUM(balance) AS total_deposits
FROM fct_monthly_balances
WHERE product_type = 'deposit'
  AND balance_date BETWEEN DATE '2026-01-01' AND DATE '2026-10-31';
