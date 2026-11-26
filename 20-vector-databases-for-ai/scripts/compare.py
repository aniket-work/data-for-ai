"""Keyword (BM25) vs semantic (dense) vs hybrid (RRF) on the labelled questions. recall@k = share of questions
whose relevant document appears in the top k (each question has one right document, two for q05)."""
import sys, os, json, statistics as st, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console; from rich.table import Table
from vdb.common import load_queries, first_hit_rank
from vdb import search as S
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
K = 5

def run(fn, qs):
    ranks, lat = {}, []
    for q in qs:
        t0 = time.perf_counter(); pts = fn(q["q"], k=10); lat.append((time.perf_counter() - t0) * 1000)
        ranks[q["id"]] = first_hit_rank([p.payload["doc_id"] for p in pts], set(q["relevant"]))
    return ranks, lat

def summary(ranks, qs, k):
    sel = [ranks[q["id"]] for q in qs]
    return sum(1 for r in sel if r and r <= k) / len(sel), sum(1 / r for r in sel if r) / len(sel)

if __name__ == "__main__":
    qs = load_queries(); S.semantic("warm up", k=1)
    res = {name: run(fn, qs) for name, fn in (("keyword", S.keyword), ("semantic", S.semantic), ("hybrid", S.hybrid))}
    t = Table(title=f"Kestrel policy search: {len(qs)} labelled questions", header_style="bold #34D399")
    t.add_column("retriever"); t.add_column("everyday wording (22)", justify="right"); t.add_column("codes and terms (10)", justify="right")
    t.add_column("all recall@1", justify="right"); t.add_column(f"all recall@{K}", justify="right"); t.add_column("MRR@10", justify="right"); t.add_column("p50 ms", justify="right")
    out = {}
    for name, (ranks, lat) in res.items():
        para = [q for q in qs if q["type"] == "paraphrase"]; ident = [q for q in qs if q["type"] == "identifier"]
        rp, _ = summary(ranks, para, K); ri, _ = summary(ranks, ident, K); ra, mrr = summary(ranks, qs, K); r1, _ = summary(ranks, qs, 1)
        t.add_row(name, f"{rp:.0%}", f"{ri:.0%}", f"{r1:.0%}", f"[bold]{ra:.0%}[/]", f"{mrr:.2f}", f"{st.median(lat):.1f}")
        out[name] = dict(recall5_paraphrase=rp, recall5_identifier=ri, recall1_all=r1, recall5_all=ra, mrr10=mrr, p50_ms=st.median(lat), ranks=ranks)
    con.print(t)
    if "--misses" in sys.argv:
        for name, (ranks, _) in res.items():
            con.print(f"[bold]{name}[/] misses@{K}: " + ", ".join(q["id"] for q in qs if not ranks[q["id"]] or ranks[q["id"]] > K))
    os.makedirs("results", exist_ok=True); json.dump(out, open("results/compare.json", "w"), indent=1)
