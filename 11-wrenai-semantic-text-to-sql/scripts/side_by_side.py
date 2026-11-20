"""Show the arms' SQL for one question side by side, with what it returns and the verdict from running it.

  python scripts/side_by_side.py q1            # raw vs wren
  python scripts/side_by_side.py q1 raw+ wren  # any two or three arms
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlglot
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from t2s import config
from t2s.score import score

qid = sys.argv[1]; arms = sys.argv[2:] or ["raw", "wren"]
truth = json.load(open(config.EVAL / "ground_truth.json"))[qid]
c = Console(force_terminal=True, color_system="truecolor", width=int(os.environ.get("COLUMNS", 146)), highlight=False)
c.print(Text(f"{qid}: {truth['question']}", style="bold"))
ans = truth["answer"]
fmt = (lambda v: f"{v:.2%}") if truth["kind"] == "rate" else (lambda v: f"{v:,.0f}")
c.print(Text("MetricFlow (Lesson 10) says: " + (", ".join(f"{k} {fmt(v)}" for k, v in ans.items()) if isinstance(ans, dict) else fmt(ans)), style="#34d399"))
TITLE = {"raw": "Raw (DDL only)", "raw+": "Raw + values", "wren": "WrenAI (MDL + rules)"}


def pretty(sql):
    try:
        return sqlglot.transpile(sql, read="duckdb", write="duckdb", pretty=True)[0]
    except Exception:
        return sql


def cell(x):
    if isinstance(x, float):
        return f"{x:.4f}" if abs(x) < 1 else f"{x:,.0f}"
    return str(x)


panels = []
for a in arms:
    rec = json.load(open(config.EVAL / "runs" / f"{a}.json")).get(qid, {})
    v, detail, rows = score(a, rec.get("sql"), ans, truth["kind"])
    col = "#34d399" if v == "correct" else "#f87171"
    body = Syntax(pretty(rec.get("sql") or "-- no SQL"), "sql", theme="monokai", word_wrap=True, background_color="default")
    res = Text("returns: ", style="bold")
    if rows and rows[1]:
        res.append("\n" + "\n".join("  " + " | ".join(cell(x) for x in r) for r in rows[1][:5]), style=col)
    else:
        res.append("nothing (0 rows)" if rows else detail, style=col)
    panels.append(Panel(Group(body, Text(""), res), title=f"[bold]{TITLE[a]}[/]", subtitle=f"[bold {col}]{v}[/]",
                        border_style=col, width=(c.width - 2) // len(arms)))
c.print(Columns(panels, equal=True, expand=True))
