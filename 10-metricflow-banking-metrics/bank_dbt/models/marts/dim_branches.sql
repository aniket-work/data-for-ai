select b.branch_id, b.branch_name, b.city, r.region_name as region
from {{ source('raw', 'branches') }} b
join {{ source('raw', 'regions') }} r using (region_id)
