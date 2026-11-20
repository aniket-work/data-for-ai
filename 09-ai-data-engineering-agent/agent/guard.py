"""Guardrails: read-only SQL for the agent, and a human approval gate for every write."""
import duckdb
from rich.panel import Panel
from rich.text import Text
from .trace import console, audit, sql as show_sql
from . import config

READ_ONLY_TYPES = {"SELECT"}

def check_read_only(query: str):
    """Allow exactly one SELECT (WITH ... SELECT included). Anything else is refused before it runs."""
    try:
        stmts = duckdb.extract_statements(query)
    except Exception as ex:
        raise ValueError(f"SQL does not parse: {ex}")
    if len(stmts) != 1:
        raise ValueError("exactly one statement is allowed")
    kind = stmts[0].type.name
    if kind not in READ_ONLY_TYPES:
        raise ValueError(f"{kind} is not allowed: this tool is read-only. Writes go through an approval tool.")

def run_read_only(query: str, limit=20):
    check_read_only(query)
    con = duckdb.connect(str(config.DB), read_only=True)      # second line of defence: a read-only connection
    try:
        cur = con.execute(query)
        cols = [d[0] for d in cur.description]; rows = cur.fetchmany(limit)
    finally:
        con.close()
    return cols, rows

def approve(action: str, details: str, sql: str | None = None, **meta):
    """Stop and ask the human. Nothing is written unless they type y."""
    console.print()
    console.print(Panel(Text(details, style="#FDE68A"), title=f"APPROVAL NEEDED: {action}", title_align="left",
                        border_style="#FBBF24", padding=(0, 1)))
    if sql:
        show_sql(sql, title="the agent wants to run")
    audit("approval_requested", action=action, **meta)
    try:
        ans = console.input("[bold #FBBF24]  Approve this write? \\[y/N] [/]").strip().lower()
    except EOFError:
        ans = ""
    ok = ans in ("y", "yes")
    feedback = ""
    if not ok:
        try:
            feedback = console.input("[bold #F87171]  What should change? [/]").strip()
        except EOFError:
            pass
    audit("approval_decision", action=action, approved=ok, feedback=feedback)
    console.print(Text("  approved by human" if ok else "  rejected by human: nothing was written",
                       style="bold #34D399" if ok else "bold #F87171"))
    return ok, feedback
