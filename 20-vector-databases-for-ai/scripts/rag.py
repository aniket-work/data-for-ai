"""Ask the policy assistant one question: python scripts/rag.py "question" [--region Prairies] [--no-retrieval]"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console; from rich.panel import Panel
from vdb.rag import answer, LLM_MODEL
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
ap = argparse.ArgumentParser(); ap.add_argument("q"); ap.add_argument("--region"); ap.add_argument("--no-retrieval", action="store_true"); a = ap.parse_args()
con.print(f"question: [bold #34D399]\"{a.q}\"[/]" + (f"   region: [bold]{a.region}[/]" if a.region else ""))
if not a.no_retrieval:
    con.print("[dim]retrieve: hybrid (BM25 + vectors, RRF), filter audience=customer, status=current" + (f", region in (ALL, {a.region})" if a.region else "") + "[/]")
txt, pts, dt = answer(a.q, a.region, not a.no_retrieval)
for i, p in enumerate(pts, 1):
    con.print(f"  [{i}] {p.payload['doc_id']:<8} {p.payload['title'][:56]:<56} {p.payload['section'][:30]}")
con.print(Panel(txt, title=f"{LLM_MODEL} on CPU ({dt:.0f} s)" + (" - NO retrieval" if a.no_retrieval else ""), border_style="#34D399" if pts else "#F59E0B", width=min(con.width, 140)))
