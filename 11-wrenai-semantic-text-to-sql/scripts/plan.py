"""Show what the Wren engine does with SQL written against MDL models: python scripts/plan.py "SELECT ..."

Runs `wren dry-plan` (no database needed) and pretty-prints the expanded DuckDB SQL next to the input.
"""
import subprocess, sys, os
import sqlglot
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel

sql = sys.argv[1]
project = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wren_bank")
out = subprocess.run(["wren", "dry-plan", "--sql", sql], cwd=project, capture_output=True, text=True, check=True).stdout.strip()
c = Console(width=146, force_terminal=True, color_system="truecolor", highlight=False)
pretty = lambda s: sqlglot.transpile(s, read="duckdb", write="duckdb", pretty=True)[0]
c.print(Panel(Syntax(pretty(sql), "sql", theme="monokai", background_color="#020617"), title="you write (models + calculated fields)", border_style="#34d399", title_align="left"))
c.print(Panel(Syntax(out, "sql", theme="monokai", background_color="#020617", word_wrap=True), title="the Wren engine plans (DuckDB SQL)", border_style="#22d3ee", title_align="left"))
