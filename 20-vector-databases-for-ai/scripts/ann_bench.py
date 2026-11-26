"""HNSW settings and quantization in Qdrant on 40,000 ticket vectors (384 dims).
recall@10 = overlap of the index's top 10 with the exact top 10 (brute force), averaged over 200 held-out queries."""
import sys, os, time, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from qdrant_client import models
from rich.console import Console; from rich.table import Table
from vdb.common import client
from vdb.tickets import vectors, query_vectors, exact_topk
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)
C = client()
CONFIGS = {
  "hnsw_m16":  dict(hnsw=models.HnswConfigDiff(m=16, ef_construct=100), q=None),
  "hnsw_m4":   dict(hnsw=models.HnswConfigDiff(m=4, ef_construct=16), q=None),
  "hnsw_sq8":  dict(hnsw=models.HnswConfigDiff(m=16, ef_construct=100),
                    q=models.ScalarQuantization(scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True))),
  "hnsw_pq16": dict(hnsw=models.HnswConfigDiff(m=16, ef_construct=100),
                    q=models.ProductQuantization(product=models.ProductQuantizationConfig(compression=models.CompressionRatio.X16, always_ram=True))),
}

def load(name, cfg, X, T):
    coll = f"tickets_{name}"
    if C.collection_exists(coll) and "--rebuild" not in sys.argv and C.count(coll).count == len(X): return None
    if C.collection_exists(coll): C.delete_collection(coll)
    C.create_collection(coll, vectors_config=models.VectorParams(size=X.shape[1], distance=models.Distance.COSINE),
                        hnsw_config=cfg["hnsw"], quantization_config=cfg["q"],
                        optimizers_config=models.OptimizersConfigDiff(default_segment_number=2, indexing_threshold=1000))
    C.create_payload_index(coll, "region", models.PayloadSchemaType.KEYWORD)
    C.create_payload_index(coll, "intent", models.PayloadSchemaType.KEYWORD)
    t0 = time.time()
    for i in range(0, len(X), 2000):
        C.upsert(coll, points=models.Batch(ids=list(range(i, min(i + 2000, len(X)))), vectors=X[i:i + 2000].tolist(),
                 payloads=[dict(intent=t["intent"], region=t["region"]) for t in T[i:i + 2000]]), wait=True)
    while True:   # wait until every vector is in the HNSW graph
        info = C.get_collection(coll)
        if info.status == models.CollectionStatus.GREEN and (info.indexed_vectors_count or 0) >= len(X): break
        time.sleep(0.5)
    return round(time.time() - t0, 1)

def bench(coll, Qv, truth, params, k=10):
    rec, lat = [], []
    for qv, tr in zip(Qv, truth):
        t0 = time.perf_counter(); pts = C.query_points(coll, query=qv.tolist(), limit=k, search_params=params).points
        lat.append((time.perf_counter() - t0) * 1000); rec.append(len({p.id for p in pts} & set(tr.tolist())) / k)
    return float(np.mean(rec)), st.median(lat), float(np.percentile(lat, 95))

if __name__ == "__main__":
    T, X = vectors(); Q, Qv = query_vectors(); truth = exact_topk(X, Qv)
    con.print(f"[bold #34D399]{len(X):,}[/] ticket vectors x {X.shape[1]} dims; {len(Q)} held-out queries; truth = exact top 10")
    builds = {n: load(n, c, X, T) for n, c in CONFIGS.items()}
    for n, b in builds.items():
        if b is not None: con.print(f"  loaded + indexed tickets_{n}: {b:.1f} s")
    for _ in range(20): C.query_points("tickets_hnsw_m16", query=Qv[0].tolist(), limit=10)   # warm up
    rows = []
    def add(name, label, params, nb):
        r, p50, p95 = bench(f"tickets_{name}", Qv, truth, params); rows.append(dict(config=label, recall10=r, p50_ms=p50, p95_ms=p95, bytes_per_vector=nb))
    add("hnsw_m16", "exact scan (no index)", models.SearchParams(exact=True), 1536)
    for ef in (10, 20, 40, 80, 160):
        add("hnsw_m16", f"HNSW m=16  ef={ef}", models.SearchParams(hnsw_ef=ef), 1536)
    for ef in (10, 40, 160):
        add("hnsw_m4", f"HNSW m=4   ef={ef}", models.SearchParams(hnsw_ef=ef), 1536)
    add("hnsw_sq8", "m=16 ef=40 + int8, no rescore", models.SearchParams(hnsw_ef=40, quantization=models.QuantizationSearchParams(rescore=False)), 384)
    add("hnsw_sq8", "m=16 ef=40 + int8, rescore 2x", models.SearchParams(hnsw_ef=40, quantization=models.QuantizationSearchParams(rescore=True, oversampling=2.0)), 384)
    add("hnsw_pq16", "m=16 ef=40 + PQ x16, no rescore", models.SearchParams(hnsw_ef=40, quantization=models.QuantizationSearchParams(rescore=False)), 96)
    add("hnsw_pq16", "m=16 ef=40 + PQ x16, rescore 2x", models.SearchParams(hnsw_ef=40, quantization=models.QuantizationSearchParams(rescore=True, oversampling=2.0)), 96)
    t = Table(title="Qdrant 1.20.2 on 40k x 384d (bge-small), 200 queries, k=10, REST on localhost", header_style="bold #34D399")
    for c, j in (("index and search setting", "left"), ("recall@10", "right"), ("p50 ms", "right"), ("p95 ms", "right"), ("bytes/vector*", "right")): t.add_column(c, justify=j)
    for r in rows: t.add_row(r["config"], f"{r['recall10']:.3f}", f"{r['p50_ms']:.2f}", f"{r['p95_ms']:.2f}", f"{r['bytes_per_vector']:,}")
    con.print(t); con.print("[dim]* stored vector size (graph links are extra). Latency includes the HTTP round trip.[/]")
    os.makedirs("results", exist_ok=True); json.dump(dict(rows=rows, build_s=builds), open("results/ann_bench.json", "w"), indent=1)
