"""Trust, but verify: the same question answered with SQL written by hand (no model involved)."""
import duckdb
from pathlib import Path
db = Path(__file__).resolve().parents[1] / "lake" / "warehouse.duckdb"
con = duckdb.connect(str(db), read_only=True)
SQL = """
SELECT r.name AS route,
       sum(t.fare) AS revenue,
       round(100 * sum(t.fare) FILTER (WHERE t.ticket_type = 'VEHICLE') / sum(t.fare), 1) AS vehicle_share_pct
FROM curated.tickets t JOIN curated.routes r ON r.route_code = t.route
WHERE t.sold_at >= DATE '2026-10-01' AND t.sold_at < DATE '2026-11-01'
GROUP BY r.name ORDER BY revenue DESC
"""
print(SQL.strip(), "\n")
cur = con.execute(SQL); cols = [d[0] for d in cur.description]
print("  ".join(f"{c:28s}" for c in cols))
for row in cur.fetchall(): print("  ".join(f"{str(v):28s}" for v in row))
