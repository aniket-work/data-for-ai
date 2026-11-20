-- one row per account per month-end: a SNAPSHOT (balances are semi-additive over time)
select m.balance_id, m.account_id, a.customer_id, a.product_id, a.branch_id, p.product_type,
       cast(m.balance_date as date) as balance_date,
       cast(m.balance as decimal(14, 2)) as balance,
       m.days_past_due,
       cast(m.interest_amount as decimal(12, 2)) as interest_amount
from {{ source('raw', 'monthly_balances') }} m
join {{ source('raw', 'accounts') }} a using (account_id)
join {{ source('raw', 'products') }} p using (product_id)
