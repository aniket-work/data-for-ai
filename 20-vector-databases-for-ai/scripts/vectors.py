"""Step 1: text in, vector out. Embed four short texts on the CPU and compare them."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rich.console import Console; from rich.table import Table
from vdb.common import embed, EMBED_MODEL
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
T = ["The ABM retained the customer's debit card.",
     "The cash machine swallowed my card!",
     "Prepay up to 15% of the mortgage principal each year.",
     "Kestrel Bay has a lighthouse and a ferry dock."]
V = embed(T)
con.print(f"model [bold]{EMBED_MODEL}[/] (local, ONNX on CPU) -> each text becomes [bold #34D399]{V.shape[1]}[/] numbers\n")
for t, v in zip(T, V):
    con.print(f"[bold]{t:<56}[/] [{', '.join(f'{x:+.3f}' for x in v[:6])}, ...]  length {np.linalg.norm(v):.3f}")
S = V @ V.T
tb = Table(title="cosine similarity (1 = same direction, 0 = unrelated)", header_style="bold #34D399")
tb.add_column("", no_wrap=True); [tb.add_column(f"#{i+1}", justify="right") for i in range(len(T))]
for i in range(len(T)):
    tb.add_row(f"#{i+1} {T[i]}", *[(f"[bold #34D399]{S[i,j]:.2f}[/]" if i != j and S[i, j] > 0.6 else f"{S[i,j]:.2f}") for j in range(len(T))])
con.print(tb)
a, b = V[0], V[1]
con.print(f"#1 vs #2   cosine {a@b/(np.linalg.norm(a)*np.linalg.norm(b)):.4f}   dot {a@b:.4f}   euclidean {np.linalg.norm(a-b):.4f}  "
          f"(unit-length vectors: dot = cosine, euclidean = sqrt(2 - 2 cos) = {np.sqrt(2-2*(a@b)):.4f})")
con.print("[dim]#1 and #2 share almost no words, yet their vectors point the same way. That is what a vector database searches.[/]")
