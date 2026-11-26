-- Ossie dataset: purchase_order
select * from {{ source('supply_chain', 'purchase_orders') }}
