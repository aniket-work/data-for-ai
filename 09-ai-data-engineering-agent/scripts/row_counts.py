"""Row counts of the curated tables, read straight from the warehouse (not from the agent's words)."""
import duckdb
from pathlib import Path
db = Path(__file__).resolve().parents[1] / "lake" / "warehouse.duckdb"
con = duckdb.connect(str(db), read_only=True)
for t in ("curated.routes", "curated.tickets", "curated.tickets_rejected"):
    print(f"{t:28s}{con.execute(f'SELECT count(*) FROM {t}').fetchall()[0][0]:>6}")
