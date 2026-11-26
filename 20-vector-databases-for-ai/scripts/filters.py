"""Metadata filters: the same vector search, restricted by region, audience and status (payload indexes)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console
from vdb import search as S
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
def show(title, q, f, k=4):
    con.print(f"\n[bold]{title}[/]  [dim]filter: {f or 'none'}[/]")
    for i, p in enumerate(S.semantic(q, k=k, f=S.flt(**f) if f else None), 1):
        pl = p.payload; tag = []
        if pl["region"] != "ALL": tag.append(pl["region"])
        if pl["audience"] != "customer": tag.append("STAFF ONLY")
        if pl["status"] != "current": tag.append("SUPERSEDED")
        con.print(f"  {i}. {pl['doc_id']:<8} {pl['title'][:58]:<58} {pl['section'][:26]:<26} " + (f"[bold #F59E0B]{' / '.join(tag)}[/]" if tag else ""))
which = sys.argv[1] if len(sys.argv) > 1 else "all"
if which in ("region", "all"):
    q = "a disaster damaged our home, can we pause the mortgage for a while?"
    con.print(f"question: [bold #34D399]\"{q}\"[/]  (customer lives in Saskatoon)")
    show("no filter", q, {}); show("region = Prairies (plus national docs)", q, dict(region="Prairies"))
if which in ("audience", "all"):
    q = "how do you check who I am before sending me a new card?"
    con.print(f"\nquestion: [bold #34D399]\"{q}\"[/]  (asked in the public chat assistant)")
    show("no filter", q, {}, 3); show("audience = customer", q, dict(audience="customer"), 3)
if which in ("status", "all"):
    q = "what is the fee for a non-sufficient funds item?"
    con.print(f"\nquestion: [bold #34D399]\"{q}\"[/]")
    show("no filter", q, {}, 3); show("status = current", q, dict(status="current"), 3)
