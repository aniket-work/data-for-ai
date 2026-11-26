-- Ossie dataset: product
select * from {{ source('supply_chain', 'products') }}
