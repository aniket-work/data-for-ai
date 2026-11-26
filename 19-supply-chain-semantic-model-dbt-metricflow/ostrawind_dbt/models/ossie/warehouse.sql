-- Ossie dataset: warehouse
select * from {{ source('supply_chain', 'warehouses') }}
