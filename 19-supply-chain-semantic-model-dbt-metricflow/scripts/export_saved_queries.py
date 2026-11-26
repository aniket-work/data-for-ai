"""Run every saved query through MetricFlow and write the results to exports/<name>.csv.
(dbt Cloud can materialize the same `exports:` as tables on a schedule; locally we write CSVs.)"""
import csv, subprocess, sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "ostrawind_dbt"; OUT = ROOT / "exports"; OUT.mkdir(exist_ok=True)
sq = yaml.safe_load((DBT / "models" / "semantic" / "saved_queries.yml").read_text())["saved_queries"]
for q in sq:
    path = OUT / f"{q['name']}.csv"
    subprocess.run(["mf", "query", "--saved-query", q["name"], "--csv", str(path), "--quiet"], cwd=DBT, check=True, capture_output=True)
    rows = sum(1 for _ in open(path)) - 1
    print(f"  {q['name']:32s} -> exports/{path.name:38s} {rows:>4} rows")
print(f"{len(sq)} saved queries exported.")
