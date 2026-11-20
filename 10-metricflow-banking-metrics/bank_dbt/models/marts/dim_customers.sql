select customer_id, segment, home_branch_id, cast(joined_on as date) as joined_on
from {{ source('raw', 'customers') }}
