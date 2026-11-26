"""Side by side: what keyword (BM25), semantic and hybrid search return for one question."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console; from rich.table import Table
from vdb import search as S
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
q = sys.argv[1]; want = sys.argv[2] if len(sys.argv) > 2 else None; k = 3
con.print(f"question: [bold #34D399]\"{q}\"[/]" + (f"   (right answer lives in [bold]{want}[/])" if want else ""))
t = Table(header_style="bold #34D399", expand=True)
for name in ("keyword (BM25)", "semantic (vectors)", "hybrid (RRF)"): t.add_column(name, ratio=1)
cols = [S.keyword(q, k), S.semantic(q, k), S.hybrid(q, k)]
for i in range(k):
    cells = []
    for pts in cols:
        if i >= len(pts): cells.append("[dim](no match)[/]"); continue
        p = pts[i].payload; mark = "[bold #34D399]" if p["doc_id"] == want else ""
        cells.append(f"{i+1}. {mark}{p['doc_id']}[/] {p['title'][:34]}\n   [dim]{p['section'][:30]}  score {pts[i].score:.3f}[/]" if mark else
                     f"{i+1}. {p['doc_id']} {p['title'][:34]}\n   [dim]{p['section'][:30]}  score {pts[i].score:.3f}[/]")
    t.add_row(*cells)
con.print(t)
