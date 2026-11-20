"""Run the hand-written SQL files in sql/handwritten and print each team's number."""
import glob, os, re, duckdb
from rich.console import Console
from rich.table import Table
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
con = duckdb.connect(os.path.join(ROOT, "warehouse", "bank.duckdb"), read_only=True)
t = Table(title="Same question, hand-written SQL", title_style="bold", header_style="bold #34d399")
for c, j in (("File", "left"), ("Team / question", "left"), ("Their number", "right")): t.add_column(c, justify=j)
for f in sorted(glob.glob(os.path.join(ROOT, "sql", "handwritten", "*.sql"))):
    sql = open(f).read(); head = re.match(r"--\s*(.*)", sql).group(1)
    v = con.execute(sql).fetchone()[0]
    s = f"{v:.2%}" if v < 1 else (f"${v:,.0f}" if "deposit" in f else f"{v:,.0f}")
    t.add_row(os.path.basename(f), head, s)
Console(width=140, force_terminal=True, color_system="truecolor").print(t)
