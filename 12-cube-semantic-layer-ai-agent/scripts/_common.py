import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
import cube_client  # noqa: E402

con = Console(highlight=False, width=146, force_terminal=True, color_system="truecolor")
ROLE_COLOR = {"exec": "bright_green", "prairies_mgr": "magenta", "central_mgr": "magenta", "marketing": "yellow"}


def fmt(v):
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)[:10] if "T00:00" in str(v) else str(v)
    if abs(f) < 1:
        return f"{f:.2%}"
    return f"{f:,.2f}" if f != int(f) else f"{int(f):,}"


def rows_table(rows, title=None):
    t = Table(title=title, title_justify="left", header_style="bold cyan", border_style="grey35")
    if not rows:
        con.print("[dim](no rows)[/]")
        return
    keys = [k for k in rows[0] if not (k.endswith("snapshot_date") or k.endswith("opened_on") or k.endswith("transaction_date"))]
    for k in keys:
        t.add_column(k.split(".")[-1], justify="right" if any(_isnum(r[k]) for r in rows) else "left")
    for r in rows:
        t.add_row(*[fmt(r[k]) for k in keys])
    con.print(t)


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def who(role):
    ctx = cube_client.ROLES[role]
    return f"[{ROLE_COLOR.get(role, 'white')}]{role}[/] [dim]security context {json.dumps(ctx)}[/]"
