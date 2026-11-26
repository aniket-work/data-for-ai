-- Ossie dataset: supplier
select * from {{ source('supply_chain', 'suppliers') }}
