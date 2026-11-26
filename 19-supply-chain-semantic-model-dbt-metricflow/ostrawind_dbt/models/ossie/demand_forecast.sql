-- Ossie dataset: demand_forecast
select * from {{ source('supply_chain', 'demand_forecasts') }}
