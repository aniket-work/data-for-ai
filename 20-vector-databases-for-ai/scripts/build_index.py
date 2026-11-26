"""Chunk the policy KB, embed it on the CPU, and load it into Qdrant (dense HNSW + BM25 + payload indexes)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qdrant_client import models
from rich.console import Console
from vdb.common import load_docs, chunk_sections, embed, client, COLLECTION, EMBED_MODEL
con = Console(width=int(os.environ.get("ASK_WIDTH", 140)), highlight=False)

def build(chunks, name=COLLECTION, distance=models.Distance.COSINE, quiet=False):
    c = client()
    if c.collection_exists(name): c.delete_collection(name)
    t0 = time.time(); vecs = embed([ch["text"] for ch in chunks], fresh="--fresh" in sys.argv); t_emb = time.time() - t0
    c.create_collection(name, vectors_config={"dense": models.VectorParams(size=vecs.shape[1], distance=distance)},
                        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100))
    # payload indexes first, so the filterable HNSW graph is built with them
    for f in ("product", "audience", "region", "status", "doc_id", "doc_type"):
        c.create_payload_index(name, f, models.PayloadSchemaType.KEYWORD)
    c.create_payload_index(name, "text", models.TextIndexParams(
        type="text", tokenizer=models.TokenizerType.WORD, lowercase=True,
        stemmer=models.SnowballParams(type="snowball", language="english"),
        stopwords=models.StopwordsSet(languages=["english"]),
        scoring=models.TextScoringParams(type="bm25")))
    c.upsert(name, points=[models.PointStruct(id=i, vector={"dense": v.tolist()}, payload=ch)
                           for i, (ch, v) in enumerate(zip(chunks, vecs))], wait=True)
    if not quiet:
        con.print(f"[bold #34D399]{len(chunks)}[/] chunks from [bold]{len({ch['doc_id'] for ch in chunks})}[/] documents")
        con.print(f"embedded with [bold]{EMBED_MODEL}[/] on CPU: {vecs.shape[1]} dims, {t_emb:.1f} s")
        con.print(f"collection [bold]{name}[/]: dense (cosine, HNSW m=16 ef_construct=100) + BM25 text index + 6 keyword payload indexes")
        con.print(f"points stored: [bold]{c.count(name).count}[/]")
    return vecs

if __name__ == "__main__":
    build(chunk_sections(load_docs()))
