"""Prints the agent's trace: every model turn, its stated reason, the tool call and the tool result."""
import json, time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from . import config

console = Console(width=140, highlight=False, force_terminal=True)
AUDIT = config.STATE / "audit.jsonl"

def audit(event, **kw):
    config.STATE.mkdir(exist_ok=True)
    with open(AUDIT, "a") as f:
        f.write(json.dumps(dict(ts=round(time.time(), 3), event=event, **kw), default=str) + "\n")

def stage(name, goal):
    console.rule(f"[bold #34D399]agent stage: {name}[/]", style="#334155")
    console.print(Text("goal  ", style="bold #94A3B8") + Text(goal, style="#E2E8F0"))
    audit("stage_start", stage=name)

def model_turn(step, seconds, tokens, thinking=None):
    console.print(Text(f"\n step {step} ", style="bold #020617 on #34D399") +
                  Text(f"  model answered in {seconds:.1f} s, {tokens} tokens", style="#64748B"))
    if thinking:
        console.print(Text("  thinking  ", style="bold #A78BFA") + Text(thinking, style="italic #A78BFA"))

def tool_call(name, args):
    reason = args.get("reason")
    shown = {k: v for k, v in args.items() if k != "reason"}
    if reason:
        console.print(Text("  reason    ", style="bold #FBBF24") + Text(str(reason), style="italic #FDE68A"))
    a = ", ".join(f"{k}=<shown below>" if k == "query" else f"{k}={json.dumps(v)}" for k, v in shown.items())
    console.print(Text("  tool      ", style="bold #22D3EE") + Text(f"{name}({a})", style="#22D3EE"))
    audit("tool_call", tool=name, args=args)

def tool_result(text, ok=True, max_lines=14):
    lines = str(text).splitlines() or [""]
    more = len(lines) - max_lines
    body = "\n".join(lines[:max_lines]) + (f"\n... {more} more lines" if more > 0 else "")
    console.print(Panel(Text(body, style="#CBD5E1" if ok else "#FCA5A5"), border_style="#334155" if ok else "#F87171",
                        title="result" if ok else "error", title_align="left", padding=(0, 1)))

def sql(code, title="SQL"):
    console.print(Panel(Syntax(code, "sql", theme="monokai", background_color="#0B1222", word_wrap=True),
                        title=title, title_align="left", border_style="#334155"))

def final(title, text):
    console.print(Panel(Text(text, style="#E2E8F0"), title=title, title_align="left", border_style="#34D399", padding=(0, 1)))
