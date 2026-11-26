-- Ossie dataset: carrier_lane_performance
select * from {{ source('supply_chain', 'carrier_performance') }}
