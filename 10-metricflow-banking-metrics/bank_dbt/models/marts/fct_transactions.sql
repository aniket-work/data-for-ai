select t.transaction_id, t.account_id, t.customer_id, a.branch_id,
       cast(t.transaction_date as date) as transaction_date, t.channel,
       cast(t.amount as decimal(12, 2)) as amount
from {{ source('raw', 'transactions') }} t
join {{ source('raw', 'accounts') }} a using (account_id)
