"""Draw the policy chunks as points: 384 dimensions squeezed to 2 with PCA (lossy, for intuition only).
Questions are projected the same way; lines go to each question's 3 nearest chunks, found in the FULL 384-d space."""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from sklearn.decomposition import PCA
from rich.console import Console
from vdb.common import load_docs, chunk_sections, embed, embed_query
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
for f in (os.environ.get("MAP_FONT", ""),):   # optional: path to a .ttf (the video used Inter)
    if f and os.path.exists(f): fm.fontManager.addfont(f); plt.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
ch = chunk_sections(load_docs()); X = embed([c["text"] for c in ch])
Q = ["the cash machine ate my card", "we were evacuated because of the wildfire", "how much notice before you raise a fee"]
QV = np.array([embed_query(q) for q in Q])
pca = PCA(2, random_state=0).fit(X); ev = pca.explained_variance_ratio_.sum()
from sklearn.manifold import TSNE
ALL = np.vstack([X, QV]); T2 = TSNE(2, perplexity=12, metric="cosine", init="pca", random_state=7).fit_transform(ALL)
VIEWS = [("PCA: straight projection", pca.transform(X), pca.transform(QV), f"keeps {ev:.0%} of the variance"),
         ("t-SNE: keeps close neighbours close", T2[:len(X)], T2[len(X):], "distances between clusters are not meaningful")]
FAM = {"cards": ("#F472B6", "cards"), "chequing": ("#38BDF8", "chequing & payments"), "savings": ("#A3E635", "savings & GIC"), "gic": ("#A3E635", "savings & GIC"),
       "mortgage": ("#FB923C", "mortgage, loans, relief"), "personal_loan": ("#FB923C", "mortgage, loans, relief"), "line_of_credit": ("#FB923C", "mortgage, loans, relief"),
       "digital": ("#C084FC", "digital & security"), "general": ("#94A3B8", "general & agreement")}
fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor="#020617")
for vi, (name, P, PQ, note) in enumerate(VIEWS):
    ax = fig.add_axes([0.03 + vi * 0.405, 0.13, 0.385, 0.70], facecolor="#020617"); seen = set()
    for c, (x, y) in zip(ch, P):
        col, lab = FAM[c["product"]]
        ax.scatter(x, y, s=95, color=col, alpha=0.9, edgecolor="#0B1222", linewidth=1, label=None if lab in seen else lab, zorder=2); seen.add(lab)
    for qi, (q, qv, (qx, qy)) in enumerate(zip(Q, QV, PQ)):
        for j in np.argsort(-(X @ qv))[:3]: ax.plot([qx, P[j, 0]], [qy, P[j, 1]], color="#34D399", lw=1.6, alpha=0.85, zorder=1)
        ax.scatter(qx, qy, marker="*", s=600, color="#34D399", edgecolor="white", linewidth=1.2, zorder=3)
        ax.annotate(f"Q{qi+1}", (qx, qy), xytext=(12, 8), textcoords="offset points", color="white", fontsize=17, zorder=4)
    ax.set_xticks([]); ax.set_yticks([]); [sp.set_color("#1E293B") for sp in ax.spines.values()]
    ax.set_title(name, color="white", fontsize=21, loc="left", pad=10); ax.text(0.0, -0.05, note, transform=ax.transAxes, color="#94A3B8", fontsize=15)
    if vi == 1: leg = ax.legend(loc="upper left", bbox_to_anchor=(1.03, 1.0), frameon=False, fontsize=15, labelcolor="white", markerscale=1.2)
fig.text(0.03, 0.92, f"{len(ch)} Kestrel policy chunks: 384-d vectors drawn in 2-d", color="white", fontsize=27)
import textwrap
fig.text(0.845, 0.50, "\n".join(textwrap.fill(f'Q{i+1}  "{q}"', 24, subsequent_indent="       ") for i, q in enumerate(Q)), color="white", fontsize=14, linespacing=1.6, va="top")
fig.text(0.03, 0.045, "Green lines = each question's 3 nearest chunks, measured in all 384 dimensions. Any 2-d picture is lossy; the database never searches it.", color="#94A3B8", fontsize=15)
os.makedirs("results", exist_ok=True); fig.savefig("results/embedding_map.png", facecolor="#020617"); plt.close(fig)
con.print(f"saved results/embedding_map.png  ({len(ch)} chunks, PCA keeps {ev:.0%} of the variance)")
for q, qv in zip(Q, QV):
    nn = np.argsort(-(X @ qv))[:3]; con.print(f'  "{q}" -> ' + ", ".join(f"{ch[j]['doc_id']} ({X[j]@qv:.2f})" for j in nn))
if "--show" in sys.argv: subprocess.run(["feh", "--fullscreen", "--auto-zoom", "--hide-pointer", "results/embedding_map.png"])
