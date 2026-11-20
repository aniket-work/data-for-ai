-- Risk team: "Delinquency rate, October 2026"
-- Drift: only counts 90+ days past due, by balance.
SELECT SUM(balance) FILTER (WHERE days_past_due >= 90) / SUM(balance) AS delinquency_rate
FROM fct_monthly_balances
WHERE product_type = 'loan' AND balance_date = DATE '2026-10-31';
