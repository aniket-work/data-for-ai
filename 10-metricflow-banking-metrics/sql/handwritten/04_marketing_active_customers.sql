-- Marketing: "Active customers, October 2026"
-- Drift: anyone with an open account counts as active.
SELECT COUNT(DISTINCT customer_id) AS active_customers
FROM fct_accounts
WHERE opened_on <= DATE '2026-10-31'
  AND (closed_on IS NULL OR closed_on > DATE '2026-10-31');
