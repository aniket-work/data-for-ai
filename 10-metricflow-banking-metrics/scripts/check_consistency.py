"""Ask MetricFlow for the same metrics at different slices (October 2026) and check they reconcile."""
import csv, os, subprocess, tempfile
from rich.console import Console
from rich.table import Table
DBT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bank_dbt")
M = ["net_interest_income", "delinquent_loans", "loan_book", "delinquency_rate"]
def mf(group_by=None):
    out = tempfile.mktemp(suffix=".csv")
    cmd = ["mf", "query", "--metrics", ",".join(M), "--start-time", "2026-10-01", "--end-time", "2026-10-31", "--csv", out, "--quiet"]
    if group_by: cmd += ["--group-by", group_by]
    subprocess.run(cmd, cwd=DBT, check=True, capture_output=True)
    rows = list(csv.DictReader(open(out))); os.remove(out); return rows
total = mf()[0]; T = {k: float(total[k]) for k in M}
c = Console(width=140, force_terminal=True, color_system="truecolor")
t = Table(title="One definition, every slice (October 2026)", title_style="bold", header_style="bold #34d399")
for col in ("Slice", "Rows", "Sum of NII", "Rate from sums", "Avg of slice rates", "Matches total?"):
    t.add_column(col, justify="left" if col == "Slice" else "right")
t.add_row("total (no group by)", "1", f"${T['net_interest_income']:,.0f}", f"{T['delinquency_rate']:.3%}", "-", "[bold #34d399]reference[/]")
for g in ("branch__region", "product__product_name", "customer__segment"):
    rows = mf(g)
    nii = sum(float(r["net_interest_income"] or 0) for r in rows)
    dl = sum(float(r["delinquent_loans"] or 0) for r in rows); lb = sum(float(r["loan_book"] or 0) for r in rows)
    rates = [float(r["delinquency_rate"]) for r in rows if r["delinquency_rate"]]
    ok = abs(nii - T["net_interest_income"]) < 0.01 and abs(dl / lb - T["delinquency_rate"]) < 1e-9
    t.add_row(g, str(len(rows)), f"${nii:,.0f}", f"{dl / lb:.3%}", f"{sum(rates) / len(rates):.3%}",
              "[bold #34d399]yes[/]" if ok else "[bold red]NO[/]")
c.print(t)
c.print("Ratios are recomputed from numerator and denominator at each grain, so averaging slice rates would be wrong.")
