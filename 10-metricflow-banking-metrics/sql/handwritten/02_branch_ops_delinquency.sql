-- Branch operations: "Delinquency rate, October 2026"
-- Drift: counts loans instead of weighting by balance.
SELECT COUNT(*) FILTER (WHERE days_past_due >= 30) * 1.0 / COUNT(*) AS delinquency_rate
FROM fct_monthly_balances
WHERE product_type = 'loan' AND balance_date = DATE '2026-10-31';
