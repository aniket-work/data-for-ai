"""Step: does the distance metric change the answer? Same chunks, four Qdrant collections, four metrics."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qdrant_client import models
from rich.console import Console; from rich.table import Table
from vdb.common import load_docs, chunk_sections, load_queries, first_hit_rank, client, embed_query
from scripts.build_index import build
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
M = {"Cosine": models.Distance.COSINE, "Dot": models.Distance.DOT, "Euclid": models.Distance.EUCLID, "Manhattan": models.Distance.MANHATTAN}
chunks = chunk_sections(load_docs()); qs = load_queries(); C = client(); top = {}
for name, d in M.items():
    build(chunks, name=f"metric_{name.lower()}", distance=d, quiet=True)
    top[name] = {q["id"]: [p.payload["chunk_id"] for p in C.query_points(f"metric_{name.lower()}", query=embed_query(q["q"]).tolist(), using="dense", limit=5, with_payload=True).points] for q in qs}
t = Table(title=f"{len(qs)} questions, top 5 chunks per metric", header_style="bold #34D399")
for c in ("metric", "same top 5 as cosine (set)", "same order", "recall@5"): t.add_column(c, justify="right" if c != "metric" else "left")
for name in M:
    same = sum(set(top[name][q]) == set(top["Cosine"][q]) for q in top[name]); order = sum(top[name][q] == top["Cosine"][q] for q in top[name])
    rec = sum(1 for q in qs if first_hit_rank([c.split("#")[0] for c in top[name][q["id"]]], set(q["relevant"])) is not None) / len(qs)
    t.add_row(name, f"{same}/{len(qs)}", f"{order}/{len(qs)}", f"{rec:.0%}")
con.print(t)
con.print("bge-small outputs unit-length vectors, so cosine, dot and euclidean rank identically. "
          "Pick the metric the model was trained with; Manhattan is not one of them.")
