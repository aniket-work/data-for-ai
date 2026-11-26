"""Same 40k ticket vectors in a vector database (Qdrant), in Postgres (pgvector) and in DuckDB (vss extension).
recall@10 vs exact top 10, 200 held-out queries. Also: what happens to a selective filter."""
import sys, os, time, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, psycopg, duckdb
from qdrant_client import models
from rich.console import Console; from rich.table import Table
from vdb.common import client
from vdb.tickets import vectors, query_vectors, exact_topk
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
PG = dict(host=os.environ.get("PG_SOCK", "/tmp/kbank_pg"), port=int(os.environ.get("PG_PORT", 55432)), user="kbank", dbname="postgres", autocommit=True)
T, X = vectors(); Q, Qv = query_vectors(); truth = exact_topk(X, Qv); rows = []
lit = lambda v: "[" + ",".join(f"{x:.6f}" for x in v) + "]"

def measure(fn, tr=truth, k=10):
    rec, lat, got = [], [], []
    for qv, t in zip(Qv, tr):
        t0 = time.perf_counter(); ids = fn(qv); lat.append((time.perf_counter() - t0) * 1000)
        got.append(len(ids)); rec.append(len(set(ids) & set(t.tolist())) / k)
    return float(np.mean(rec)), st.median(lat), float(np.mean(got))

def add(engine, setting, build, r):
    rows.append(dict(engine=engine, setting=setting, build_s=build, recall10=r[0], p50_ms=r[1], rows=r[2]))
    con.print(f"  {engine:<16} {setting:<34} recall@10 {r[0]:.3f}   p50 {r[1]:.2f} ms" + (f"   build {build:.1f} s" if build else ""))

# ------------------------------------------------ pgvector
con.print("[bold #34D399]pgvector 0.8 in PostgreSQL 17[/]")
pg = psycopg.connect(**PG); cur = pg.cursor()
cur.execute("CREATE EXTENSION IF NOT EXISTS vector; DROP TABLE IF EXISTS tickets;"
            "CREATE TABLE tickets (id int PRIMARY KEY, intent text, region text, embedding vector(384))")
t0 = time.time()
with cur.copy("COPY tickets (id, intent, region, embedding) FROM STDIN") as cp:
    for i, (t, v) in enumerate(zip(T, X)): cp.write_row((i, t["intent"], t["region"], lit(v)))
con.print(f"  loaded {len(X):,} rows in {time.time()-t0:.1f} s")
def pgq(sql, extra=()):
    return lambda qv: [r[0] for r in cur.execute(sql, (lit(qv), *extra), prepare=True).fetchall()]
KNN = "SELECT id FROM tickets ORDER BY embedding <=> %s::vector LIMIT 10"
cur.execute("SET max_parallel_workers_per_gather = 0")
add("pgvector", "exact scan (no index)", None, measure(pgq(KNN)))
t0 = time.time(); cur.execute("CREATE INDEX t_hnsw ON tickets USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"); b = time.time() - t0
cur.execute("SET hnsw.ef_search = 40"); add("pgvector", "HNSW m=16, ef_search=40", b, measure(pgq(KNN)))
cur.execute("DROP INDEX t_hnsw")
t0 = time.time(); cur.execute("CREATE INDEX t_ivf ON tickets USING ivfflat (embedding vector_cosine_ops) WITH (lists = 200)"); b = time.time() - t0
for pr in (1, 5, 20):
    cur.execute(f"SET ivfflat.probes = {pr}"); add("pgvector", f"IVFFlat lists=200, probes={pr}", b if pr == 1 else None, measure(pgq(KNN)))
cur.execute("DROP INDEX t_ivf"); cur.execute("CREATE INDEX t_hnsw ON tickets USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")

# ------------------------------------------------ DuckDB vss
con.print("[bold #34D399]DuckDB 2.0 + vss extension (in-memory)[/]")
dd = duckdb.connect(); dd.execute(f"SET extension_directory='{os.path.abspath('.cache/duckdb_ext')}'")
try: dd.execute("INSTALL vss; LOAD vss")
except duckdb.Error:   # plain-http extension download blocked on some networks: fetch over https, install from file
    import urllib.request, gzip; f = os.path.abspath(".cache/vss.duckdb_extension")
    url = f"https://extensions.duckdb.org/v{duckdb.__version__}/linux_amd64/vss.duckdb_extension.gz"
    open(f, "wb").write(gzip.decompress(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8"})).read())); dd.execute(f"INSTALL '{f}'; LOAD vss")
dd.execute("CREATE TABLE tickets (id INT, embedding FLOAT[384])")
import pandas as pd
dd.register("df", pd.DataFrame({"id": np.arange(len(X)), "embedding": list(X)})); dd.execute("INSERT INTO tickets SELECT id, embedding::FLOAT[384] FROM df")
DQ = "SELECT id FROM tickets ORDER BY array_cosine_distance(embedding, ?::FLOAT[384]) LIMIT 10"
duck = lambda qv: [r[0] for r in dd.execute(DQ, [qv.tolist()]).fetchall()]
add("DuckDB", "exact scan (no index)", None, measure(duck))
t0 = time.time(); dd.execute("CREATE INDEX t_hnsw ON tickets USING HNSW (embedding) WITH (metric = 'cosine')"); b = time.time() - t0
add("DuckDB vss", "HNSW defaults (cosine)", b, measure(duck))

# ------------------------------------------------ Qdrant (collection built by ann_bench.py)
con.print("[bold #34D399]Qdrant 1.20.2[/]")
C = client()
qd = lambda qv, f=None, ef=40: [p.id for p in C.query_points("tickets_hnsw_m16", query=qv.tolist(), limit=10, query_filter=f, search_params=models.SearchParams(hnsw_ef=ef)).points]
add("Qdrant", "HNSW m=16, hnsw_ef=40", None, measure(qd))

# ------------------------------------------------ a selective filter
mask = np.array([t["intent"] == "gic" and t["region"] == "Prairies" for t in T]); idx = np.where(mask)[0]
ftruth = idx[exact_topk(X[idx], Qv)]
con.print(f"\n[bold]Filtered search[/]: intent = 'gic' AND region = 'Prairies' matches {mask.sum():,} of {len(X):,} rows ({mask.mean():.1%})")
FQ = "SELECT id FROM tickets WHERE intent = 'gic' AND region = 'Prairies' ORDER BY embedding <=> %s::vector LIMIT 10"
cur.execute("ANALYZE tickets; SET hnsw.ef_search = 40; SET hnsw.iterative_scan = off")
plan = lambda: " ".join(r[0] for r in cur.execute("EXPLAIN " + FQ.replace("%s", "'" + lit(Qv[0]) + "'")).fetchall())
scan = "Seq Scan" if "Seq Scan" in plan() else "HNSW index"
r = measure(pgq(FQ), ftruth); rows.append(dict(engine="pgvector", setting=f"planner's choice ({scan})", recall10=r[0], p50_ms=r[1], rows=r[2]))
con.print(f"  pgvector, planner's own choice    : {scan}, {r[2]:.1f} rows, recall@10 {r[0]:.3f}, p50 {r[1]:.2f} ms")
cur.execute("SET enable_seqscan = off")   # what happens when the HNSW index IS used (bigger tables, other stats)
assert "t_hnsw" in plan()
r = measure(pgq(FQ), ftruth); rows.append(dict(engine="pgvector", setting="HNSW + WHERE, iterative off", recall10=r[0], p50_ms=r[1], rows=r[2]))
con.print(f"  pgvector HNSW, iterative scan off : {r[2]:.1f} rows returned on average (asked for 10), recall@10 {r[0]:.3f}")
cur.execute("SET hnsw.iterative_scan = relaxed_order")
r = measure(pgq(FQ), ftruth); rows.append(dict(engine="pgvector", setting="HNSW + WHERE, iterative relaxed", recall10=r[0], p50_ms=r[1], rows=r[2]))
con.print(f"  pgvector HNSW, iterative relaxed  : {r[2]:.1f} rows, recall@10 {r[0]:.3f}, p50 {r[1]:.2f} ms")
F = models.Filter(must=[models.FieldCondition(key="intent", match=models.MatchValue(value="gic")), models.FieldCondition(key="region", match=models.MatchValue(value="Prairies"))])
r = measure(lambda qv: qd(qv, F), ftruth); rows.append(dict(engine="Qdrant", setting="payload index + query planner", recall10=r[0], p50_ms=r[1], rows=r[2]))
con.print(f"  Qdrant, payload index + planner   : {r[2]:.1f} rows, recall@10 {r[0]:.3f}, p50 {r[1]:.2f} ms")
os.makedirs("results", exist_ok=True); json.dump(rows, open("results/pg_duckdb.json", "w"), indent=1)
