-- Ossie dataset: inventory_snapshot
select * from {{ source('supply_chain', 'inventory_snapshots') }}
