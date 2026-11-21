"""Copy the Lesson 10 warehouse into warehouse/bank.duckdb in a storage format Cube's DuckDB driver can read.

Lesson 10 writes its DuckDB file with duckdb 2.x; Cube 1.8's Node driver bundles duckdb 1.5, which reads
storage version v1.2.0. So we copy the six dbt marts into a new file written with STORAGE_VERSION 'v1.2.0'.

    python scripts/make_warehouse.py            # reads ../10-metricflow-banking-metrics/warehouse/bank.duckdb
"""
import pathlib, sys
import duckdb

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE.parent / "10-metricflow-banking-metrics" / "warehouse" / "bank.duckdb"
DST = HERE / "warehouse" / "bank.duckdb"
TABLES = ["dim_branches", "dim_products", "dim_customers", "fct_monthly_balances", "fct_accounts", "fct_transactions"]

if not SRC.exists():
    sys.exit("Build the Lesson 10 warehouse first: see README, step 1.")
DST.parent.mkdir(exist_ok=True)
DST.unlink(missing_ok=True)
con = duckdb.connect()
con.execute(f"ATTACH '{SRC}' AS src (READ_ONLY)")
con.execute(f"ATTACH '{DST}' AS dst (STORAGE_VERSION 'v1.2.0')")
for t in TABLES:
    con.execute(f"CREATE TABLE dst.main.{t} AS SELECT * FROM src.main.{t}")
    print(f"{t:22s} {con.execute(f'SELECT count(*) FROM dst.main.{t}').fetchone()[0]:>8,} rows")
con.execute("DETACH dst")
print("wrote warehouse/bank.duckdb")
