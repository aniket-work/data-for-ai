"""8 questions with known answers in the policy KB (r8 is NOT in the KB: the right answer is 'I don't know').
Scored by a plain string check on the answer, with and without retrieval. Same local model, temperature 0."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console; from rich.table import Table
from vdb.common import ROOT
from vdb.rag import answer, LLM_MODEL
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
QS = [json.loads(l) for l in open(os.path.join(ROOT, "eval", "rag_questions.jsonl"))]
t = Table(title=f"RAG check: {LLM_MODEL} (Q4, CPU), temperature 0", header_style="bold #34D399")
for c in ("id", "question", "expected", "no retrieval", "with retrieval", "cited"): t.add_column(c)
out = []; score = {"no": 0, "rag": 0}
for q in QS:
    ok = lambda s: any(e.lower() in s.lower() for e in q["expect_any"])
    a0, _, _ = answer(q["q"], q["region"], use_retrieval=False); a1, pts, _ = answer(q["q"], q["region"])
    score["no"] += ok(a0); score["rag"] += ok(a1)
    cited = sorted({p.payload["doc_id"] for p in pts if f"[{p.payload['doc_id']}]" in a1})
    t.add_row(q["id"], q["q"][:52], q["expect_any"][0] if q["id"] != "r8" else "I don't know", "[#34D399]yes[/]" if ok(a0) else "[#F87171]no[/]",
              "[#34D399]yes[/]" if ok(a1) else "[#F87171]no[/]", ", ".join(cited))
    out.append(dict(id=q["id"], q=q["q"], no_retrieval=a0, rag=a1, ok_no=ok(a0), ok_rag=ok(a1), cited=cited))
t.add_row("", "[bold]total[/]", "", f"[bold]{score['no']}/{len(QS)}[/]", f"[bold]{score['rag']}/{len(QS)}[/]", "")
con.print(t)
os.makedirs("results", exist_ok=True); json.dump(dict(score=score, n=len(QS), answers=out), open("results/rag_eval.json", "w"), indent=1)
