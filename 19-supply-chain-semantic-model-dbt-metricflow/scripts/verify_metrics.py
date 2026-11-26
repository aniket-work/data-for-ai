"""Check every Ossie metric two ways, month by month:
   (1) plain SQL compiled straight from the Ossie expression, run on DuckDB
   (2) MetricFlow, through the dbt project generated from the same Ossie file
"""
import csv, os, re, subprocess, tempfile
from pathlib import Path
import duckdb, yaml
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "ostrawind_dbt"
m = yaml.safe_load((ROOT / "model" / "ostrawind_supply_chain.ossie.yaml").read_text())
ds = {d["name"]: d for d in m["datasets"]}
fexpr = {(d["name"], f["name"]): f["expression"]["sql"] for d in m["datasets"] for f in d["fields"]}
first_time = {d["name"]: next((f["expression"]["sql"] for f in d["fields"] if f.get("dimension", {}).get("is_time")), None) for d in m["datasets"]}

def fact_of(sql): return re.search(r"(\w+)\.\w+", sql).group(1)

def direct(metric_sql):
    dset = fact_of(metric_sql)
    body = re.sub(r"(\w+)\.(\w+)", lambda g: f"({fexpr[(g.group(1), g.group(2))]})", metric_sql)
    body = body.replace(") / SUM(", ") / NULLIF(SUM(")  # keep ratios safe
    if "NULLIF(" in body: body += ", 0)"
    sql = (f"select date_trunc('month', {first_time[dset]})::date as month, ({body})::double as v "
           f"from {ds[dset]['source']} group by 1")
    con = duckdb.connect(str(ROOT / "warehouse" / "ostrawind.duckdb"), read_only=True)
    rows = {str(r[0] or "no date"): r[1] for r in con.execute(sql).fetchall() if r[1] is not None}
    con.close()
    return rows

def via_mf(metrics):
    out = tempfile.mktemp(suffix=".csv")
    subprocess.run(["mf", "query", "--metrics", ",".join(metrics), "--group-by", "metric_time__month",
                    "--csv", out, "--quiet"], cwd=DBT, check=True, capture_output=True)
    rows = list(csv.DictReader(open(out))); os.remove(out)
    res = {k: {} for k in metrics}
    for r in rows:
        month = r["metric_time__month"][:10] or "no date"
        for k in metrics:
            if r[k] not in ("", None): res[k][month] = float(r[k])
    return res

by_fact = {}
for x in m["metrics"]:
    by_fact.setdefault(fact_of(x["expression"]["sql"]), []).append(x)

c = Console(width=118, force_terminal=True, color_system="truecolor")
t = Table(title="Every Ossie metric: plain SQL vs MetricFlow, month by month", title_style="bold", header_style="bold #34d399")
for col in ("Metric", "Dataset", "Months equal", "Oct 2026, plain SQL", "Oct 2026, MetricFlow", "Match"):
    t.add_column(col, justify="left" if col in ("Metric", "Dataset") else "right", no_wrap=True)
OCT = "2026-10-01"
def fmt(v):
    if v is None: return "-"
    return f"{v:.4f}" if abs(v) < 2 and v != int(v) else f"{v:,.2f}" if v != int(v) else f"{v:,.0f}"
ok = 0
for dset, xs in by_fact.items():
    mf = via_mf([x["name"] for x in xs])
    for x in xs:
        a, b = direct(x["expression"]["sql"]), mf[x["name"]]
        eq = sum(1 for k in b if k in a and abs((a[k] or 0) - b[k]) <= 1e-6 * max(1, abs(b[k])))
        same = set(a) == set(b) and eq == len(b)
        ok += same
        t.add_row(x["name"], dset, f"{eq}/{len(b)}", fmt(a.get(OCT)), fmt(b.get(OCT)),
                  "[bold #34d399]yes[/]" if same else "[bold red]NO[/]")
c.print(t)
c.print(f"[bold #34d399]{ok} of {len(m['metrics'])} metrics match in every month.[/]")
