"""Step: how you cut documents changes what you can find. Same documents, three chunking strategies.
Table A: the 32 labelled questions (short documents, right document in top k).
Table B: 6 questions about the long account agreement (AGR-01, ~1,000 words): a hit needs a top-3 chunk
that CONTAINS the answer sentence, and we count the words a RAG prompt would receive."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console; from rich.table import Table
from vdb.common import ROOT, load_docs, chunk_sections, chunk_fixed, chunk_whole, load_queries, first_hit_rank
from vdb import search as S
from scripts.build_index import build
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
docs = load_docs(); qs = load_queries()
LQ = [json.loads(l) for l in open(os.path.join(ROOT, "eval", "long_doc_queries.jsonl"))]
norm = lambda s: " ".join(s.lower().split())
STRATS = [("whole document, 1 vector each", "chunk_whole", chunk_whole(docs)),
          ("fixed 40 words, 10 overlap", "chunk_fixed", chunk_fixed(docs)),
          ("by section + title prefix", "chunk_sections", chunk_sections(docs))]
A = Table(title=f"A. {len(qs)} labelled questions (semantic search)", header_style="bold #34D399")
for c in ("strategy", "chunks", "avg words", "recall@1", "recall@3", "MRR@10"): A.add_column(c, justify="left" if c == "strategy" else "right")
B = Table(title=f"B. {len(LQ)} questions inside the ~1,000-word account agreement", header_style="bold #34D399")
for c in ("strategy", "answer in top 3", "words sent to the LLM (top 3)"): B.add_column(c, justify="left" if c == "strategy" else "right")
out = {}
for label, coll, ch in STRATS:
    build(ch, name=coll, quiet=True)
    ranks = [first_hit_rank([p.payload["doc_id"] for p in S.semantic(q["q"], k=10, coll=coll)], set(q["relevant"])) for q in qs]
    r = lambda k: sum(1 for x in ranks if x and x <= k) / len(qs)
    A.add_row(label, str(len(ch)), f"{sum(len(c['text'].split()) for c in ch)/len(ch):.0f}", f"{r(1):.0%}", f"{r(3):.0%}", f"{sum(1/x for x in ranks if x)/len(qs):.2f}")
    hits = words = 0
    for q in LQ:
        top = S.semantic(q["q"], k=3, coll=coll)
        hits += any(norm(q["answer_in"]) in norm(p.payload["text"]) for p in top); words += sum(len(p.payload["text"].split()) for p in top)
    B.add_row(label, f"{hits}/{len(LQ)}", f"{words/len(LQ):,.0f}")
    out[coll] = dict(chunks=len(ch), recall1=r(1), recall3=r(3), long_hits=hits, long_words=words / len(LQ))
con.print(A); con.print(B)
con.print("[dim]bge-small reads at most 512 tokens, so a whole-document vector never 'sees' the end of a long agreement.[/]")
os.makedirs("results", exist_ok=True); json.dump(out, open("results/chunking.json", "w"), indent=1)
