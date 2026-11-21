"""Ask the agent the 8 Lesson 11 questions through Cube (MCP) and check every number
against the Lesson 10 MetricFlow ground truth (eval/ground_truth.json)."""
import asyncio
import json
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from ask import run

ROOT = Path(__file__).resolve().parent.parent
QS = yaml.safe_load((ROOT / "eval" / "questions.yml").read_text())
TRUTH = json.loads((ROOT / "eval" / "ground_truth.json").read_text())
con = Console(highlight=False)


def numbers(rows):
    """Every numeric value in the rows, keyed by the row's text values."""
    out = {}
    for r in rows or []:
        keys = tuple(str(v) for v in r.values() if isinstance(v, str) and not _num(v) and "T00:" not in v)
        for k, v in r.items():
            if _num(v) and not k.endswith(("month", "quarter", "year")):
                out.setdefault(keys, []).append(float(v))
    return out


def _num(v):
    try:
        float(v)
        return v is not None
    except (TypeError, ValueError):
        return False


def close(a, b, kind="amount"):
    if kind == "rate":                       # within 0.05 percentage points
        return abs(a - b) <= 0.0005
    return abs(a - b) <= max(abs(b) * 0.005, 0.5)   # within 0.5%


def score(rows, truth, kind="amount"):
    got = numbers(rows)
    if isinstance(truth, dict):
        for key, want in truth.items():
            vals = [v for k, vs in got.items() if key in k for v in vs]
            if len(truth) == 1 and not vals:  # filtered question: one scalar row is fine
                vals = [v for vs in got.values() for v in vs]
            if not any(close(v, want, kind) for v in vals):
                return False
        return True
    return any(close(v, truth, kind) for vs in got.values() for v in vs)


async def main():
    ids = sys.argv[1:] or [q["id"] for q in QS]
    results = {}
    for q in QS:
        if q["id"] not in ids:
            continue
        con.rule(q["id"])
        try:
            answer, rows = await run(q["question"])
        except Exception as e:
            answer, rows = f"run failed: {e}", None
        ok = score(rows, TRUTH[q["id"]]["answer"], TRUTH[q["id"]]["kind"])
        results[q["id"]] = {"question": q["question"], "correct": ok, "answer": answer, "rows": rows}
        con.print("[green]CORRECT[/]" if ok else "[red]WRONG[/]")
    t = Table(title="Agent over Cube MCP vs Lesson 10 ground truth")
    t.add_column("q"); t.add_column("question"); t.add_column("result")
    for k, r in results.items():
        t.add_row(k, r["question"], "[green]correct[/]" if r["correct"] else "[red]wrong[/]")
    con.print(t)
    con.print(f"[bold]{sum(r['correct'] for r in results.values())}/{len(results)} correct[/]")
    if len(results) == len(QS):
        (ROOT / "eval" / "scoreboard.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
