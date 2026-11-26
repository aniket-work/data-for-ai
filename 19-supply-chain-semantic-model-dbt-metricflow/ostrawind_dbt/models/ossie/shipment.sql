-- Ossie dataset: shipment
select * from {{ source('supply_chain', 'shipments') }}
