"""Print the agent's audit log: every tool call, approval request and human decision (state/audit.jsonl)."""
import json, sys
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table

p = Path(__file__).resolve().parents[1] / "state" / "audit.jsonl"
rows = [json.loads(l) for l in open(p)]
only = sys.argv[1:]                      # e.g. approval_requested approval_decision
t = Table(title=f"audit log: {len(rows)} events", title_style="bold #34D399", header_style="bold #34D399", border_style="#334155")
for c in ("time", "event", "detail"): t.add_column(c)
for r in rows:
    if only and r["event"] not in only: continue
    d = r.get("tool") or r.get("stage") or r.get("action", "")
    if r["event"] == "approval_decision":
        d += "  ->  " + ("APPROVED" if r["approved"] else "REJECTED") + (f"  ({r['feedback']})" if r.get("feedback") else "")
    style = "#FBBF24" if r["event"].startswith("approval") else ("#34D399" if r["event"] == "stage_start" else "#CBD5E1")
    t.add_row(datetime.fromtimestamp(r["ts"]).strftime("%H:%M:%S"), r["event"], d, style=style)
Console(width=140).print(t)
