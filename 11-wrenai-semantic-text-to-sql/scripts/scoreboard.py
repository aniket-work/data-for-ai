"""Score eval/runs/raw.json and eval/runs/wren.json against eval/ground_truth.json.

  python scripts/scoreboard.py            # table + accuracy; writes eval/scoreboard.json
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console
from rich.table import Table
from t2s import config
from t2s.score import score

truth = json.load(open(config.EVAL / "ground_truth.json"))
runs = {a: json.load(open(config.EVAL / "runs" / f"{a}.json")) for a in ("raw", "raw+", "wren") if (config.EVAL / "runs" / f"{a}.json").exists()}
c = Console(force_terminal=True, color_system="truecolor", width=150, highlight=False)
t = Table(title="Same model, same questions: raw text-to-SQL vs WrenAI (scored by running the SQL)", header_style="bold #34d399")
t.add_column("#"); t.add_column("Question", max_width=58)
for a in runs:
    t.add_column({"raw": "Raw (DDL only)", "raw+": "Raw + values", "wren": "WrenAI (MDL + rules)"}[a], justify="center")
STYLE = {"correct": "[bold #34d399]correct[/]", "wrong": "[bold #f87171]wrong[/]", "error": "[bold #f87171]error[/]", "no answer": "[bold #f87171]no answer[/]"}
board, ok = {}, {a: 0 for a in runs}
for qid, q in truth.items():
    cells = []
    for a, r in runs.items():
        rec = r.get(qid, {})
        v, detail, _ = score(a, rec.get("sql"), q["answer"], q["kind"])
        board.setdefault(qid, {})[a] = {"verdict": v, "detail": detail, "sql": rec.get("sql"), "seconds": rec.get("seconds")}
        ok[a] += v == "correct"
        cells.append(STYLE[v])
    t.add_row(qid, q["question"], *cells)
t.add_row("", "[bold]Accuracy[/]", *[f"[bold]{ok[a]}/{len(truth)}[/]" for a in runs])
c.print(t)
json.dump({"accuracy": {a: f"{ok[a]}/{len(truth)}" for a in runs}, "questions": board}, open(config.EVAL / "scoreboard.json", "w"), indent=2)
