select product_id, product_name, product_type, product_family, annual_rate
from {{ source('raw', 'products') }}
