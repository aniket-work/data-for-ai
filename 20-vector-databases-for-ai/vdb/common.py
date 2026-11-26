"""Shared helpers: load the policy KB, chunk it, embed it locally, talk to Qdrant."""
import os, re, json, time, hashlib, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "kb")
CACHE = os.path.join(ROOT, ".cache"); os.makedirs(CACHE, exist_ok=True)
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")   # 384 dims, runs on CPU (ONNX)
COLLECTION = "kestrel_policies"

# ---------------------------------------------------------------- documents
def load_docs():
    docs = []
    for p in sorted(glob.glob(os.path.join(KB_DIR, "*.md"))):
        raw = open(p).read(); _, fm, body = raw.split("---\n", 2)
        meta = dict(line.split(": ", 1) for line in fm.strip().splitlines())
        title = re.search(r"^# (.+)$", body, re.M).group(1)
        sections = [(h.strip(), " ".join(t.split())) for h, t in re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", body, re.M | re.S)]
        docs.append(dict(meta, title=title, sections=sections))
    return docs

# ---------------------------------------------------------------- chunking
def chunk_sections(docs):
    """One chunk per section, prefixed with the document title (keeps context)."""
    out = []
    for d in docs:
        for i, (h, t) in enumerate(d["sections"]):
            out.append(_chunk(d, i, f"{d['title']} - {h}: {t}", h))
    return out

def chunk_fixed(docs, words=40, overlap=10):
    """Fixed-size word windows over the whole document, ignoring structure."""
    out = []
    for d in docs:
        w = " ".join(t for _, t in d["sections"]).split(); i = k = 0
        while i < len(w):
            out.append(_chunk(d, k, " ".join(w[i:i + words]), f"words {i}-{min(i + words, len(w))}"))
            k += 1; i += words - overlap
    return out

def chunk_whole(docs):
    """No chunking: the whole document is one vector."""
    return [_chunk(d, 0, d["title"] + ". " + " ".join(f"{h}: {t}" for h, t in d["sections"]), "whole document") for d in docs]

def _chunk(d, i, text, section):
    return dict(chunk_id=f"{d['id']}#{i}", doc_id=d["id"], title=d["title"], section=section, text=text,
                product=d["product"], doc_type=d["doc_type"], audience=d["audience"], region=d["region"],
                effective=d["effective"], status=d["status"])

# ---------------------------------------------------------------- embeddings (local, cached)
_model = None
def model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(EMBED_MODEL, cache_dir=os.environ.get("FASTEMBED_CACHE_PATH"))
    return _model

def embed(texts, kind="passage", fresh=False):
    """bge models expect a short instruction on queries; passages are embedded as-is."""
    key = hashlib.sha1((EMBED_MODEL + kind + "\x00".join(texts)).encode()).hexdigest()[:16]
    p = os.path.join(CACHE, f"emb_{key}.npy")
    if os.path.exists(p) and not fresh: return np.load(p)
    m = model()
    vecs = np.array(list(m.query_embed(texts) if kind == "query" else m.passage_embed(texts)), dtype=np.float32)
    np.save(p, vecs); return vecs

def embed_query(q):
    return np.array(next(iter(model().query_embed([q]))), dtype=np.float32)

# ---------------------------------------------------------------- eval
def load_queries():
    return [json.loads(l) for l in open(os.path.join(ROOT, "eval", "queries.jsonl")) if l.strip()]

def first_hit_rank(doc_ids, relevant):
    for r, d in enumerate(doc_ids, 1):
        if d in relevant: return r
    return None

def client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL, timeout=120)
