-- one row per account; loans carry the principal at origination
select a.account_id, a.customer_id, a.product_id, a.branch_id, p.product_type,
       cast(a.opened_on as date) as opened_on, cast(a.closed_on as date) as closed_on,
       case when a.closed_on is null then 'open' else 'closed' end as account_status,
       cast(a.original_principal as decimal(14, 2)) as original_principal
from {{ source('raw', 'accounts') }} a
join {{ source('raw', 'products') }} p using (product_id)
