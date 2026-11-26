-- Ossie dataset: carrier
select * from {{ source('supply_chain', 'carriers') }}
