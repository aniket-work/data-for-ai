"""SQL API: Cube speaks the Postgres wire protocol (port 15432). Views look like tables; MEASURE() aggregates."""
import sys
from rich.syntax import Syntax
from _common import con, who, cube_client
from rich.table import Table
from _common import fmt

user = sys.argv[1] if len(sys.argv) > 1 else "exec"
sql = """SELECT region,
       MEASURE(delinquency_rate) AS delinquency_rate,
       MEASURE(loan_book)        AS loan_book
FROM balance_sheet
WHERE snapshot_date >= '2026-10-01' AND snapshot_date < '2026-11-01'
GROUP BY region
ORDER BY 2 DESC"""
con.print(f"[bold]SQL API[/]  psql -h localhost -p 15432 -U {user}   as", who(user))
con.print(Syntax(sql, "sql", theme="monokai", background_color="#020617"))
try:
    cols, rows = cube_client.sql_api(sql, user)
except Exception as e:
    import re
    m = re.search(r"Invalid identifier '#?(\w+)'", str(e))
    con.print(f"[bold red]refused:[/] {m.group(1) + ' is not in the schema this user can see' if m else str(e).splitlines()[0][:120]}")
    raise SystemExit(0)
t = Table(header_style="bold cyan", border_style="grey35")
for c in cols:
    t.add_column(c, justify="left" if c == "region" else "right")
for r in rows:
    t.add_row(*[fmt(v) for v in r])
con.print(t)
