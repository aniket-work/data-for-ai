"""REST: POST a semantic query (JSON) to Cube's /cubejs-api/v1/load. Cube writes the SQL."""
import json
from _common import con, rows_table, who, cube_client

query = {
    "measures": ["balance_sheet.total_deposits", "balance_sheet.loan_book", "balance_sheet.delinquency_rate"],
    "timeDimensions": [{"dimension": "balance_sheet.snapshot_date", "dateRange": ["2026-10-01", "2026-10-31"]}],
}
con.print("[bold]REST[/]  POST http://localhost:4000/cubejs-api/v1/load   as", who("exec"))
con.print_json(json.dumps(query))
rows_table(cube_client.load(query, "exec")["data"], "October 31, 2026")
