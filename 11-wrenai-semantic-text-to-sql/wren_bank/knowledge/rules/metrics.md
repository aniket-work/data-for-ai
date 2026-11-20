## Metric definitions (approved by Finance and Risk, same as the Lesson 10 MetricFlow metrics)
- **Total deposits** = SUM(deposit_balance) from monthly_balances at the LAST month-end of the period.
- **Loan book** = SUM(loan_balance) from monthly_balances at the last month-end of the period.
- **Delinquency rate** = SUM(delinquent_loan_balance) / SUM(loan_balance) at the last month-end of the period. By balance, 30+ days past due, loans only. Never count loans, never average rates.
- **Net interest income (NII)** = SUM(net_interest_income) over every month-end in the period (interest earned on loans minus interest paid on deposits).
- **Active customers** = COUNT(DISTINCT customer_id) in transactions with transaction_date in the 90 days ending on the period end: `transaction_date BETWEEN <period_end> - INTERVAL 89 DAY AND <period_end>`.
- **Loan originations** = SUM(loan_origination_amount) from accounts by opened_on. **Year to date** = from January 1 of the current year to now.
- **Average loan size** = SUM(loan_origination_amount) / COUNT(loan_origination_amount) for loans opened in the period.
