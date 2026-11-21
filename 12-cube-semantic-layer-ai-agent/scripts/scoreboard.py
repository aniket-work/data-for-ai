"""Print the last evaluation (eval/scoreboard.json, written by agent/eval.py)."""
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
board = json.loads((ROOT / "eval" / "scoreboard.json").read_text())
con = Console(highlight=False, width=146, force_terminal=True, color_system="truecolor")
t = Table(title="AI agent over Cube (MCP), 8 bank questions, checked against Lesson 10 MetricFlow",
          title_justify="left", header_style="bold cyan", border_style="grey35")
t.add_column("q"); t.add_column("question"); t.add_column("agent's answer (short)", max_width=62); t.add_column("result", justify="center")
for k, r in board.items():
    ans = " ".join(r["answer"].split())
    t.add_row(k, r["question"], ans[:120] + ("..." if len(ans) > 120 else ""),
              "[bold green]correct[/]" if r["correct"] else "[bold red]wrong[/]")
con.print(t)
n = sum(r["correct"] for r in board.values())
con.print(f"[bold]{n}/{len(board)} correct[/]   [dim]Lesson 11 with the same model: raw schema 0/8, WrenAI 6/8[/]")
