"""One query, three roles. Cube applies the view's access_policy from each caller's security context."""
import sys
from _common import con, rows_table, who, cube_client

QUERIES = {
    "region": {"measures": ["balance_sheet.delinquency_rate", "balance_sheet.total_deposits"],
               "dimensions": ["balance_sheet.region"],
               "timeDimensions": [{"dimension": "balance_sheet.snapshot_date", "dateRange": ["2026-10-01", "2026-10-31"]}]},
    "customers": {"measures": ["lending.loan_originations"], "dimensions": ["lending.customer_id", "lending.region"],
                  "timeDimensions": [{"dimension": "lending.opened_on", "dateRange": ["2026-01-01", "2026-10-31"]}],
                  "order": {"lending.loan_originations": "desc"}, "limit": 3},
}
name = sys.argv[1] if len(sys.argv) > 1 else "region"
q = QUERIES[name]
con.print(f"[bold]same query[/]  measures {[m.split('.')[-1] for m in q['measures']]}  dimensions {[d.split('.')[-1] for d in q['dimensions']]}")
for role in ["exec", "prairies_mgr", "marketing"]:
    con.print()
    con.print("as", who(role))
    try:
        rows_table(cube_client.load(q, role)["data"])
    except Exception as e:
        con.print(f"[bold red]denied:[/] {str(e).split(' Please make it visible')[0].replace('Error: ', '')}")
        if name == "region":
            q2 = dict(q, measures=["balance_sheet.total_deposits"])
            con.print("[dim]... but marketing may ask for deposits:[/]")
            rows_table(cube_client.load(q2, role)["data"])
