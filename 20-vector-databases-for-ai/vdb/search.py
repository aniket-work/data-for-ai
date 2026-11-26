"""The three retrievers we compare, all inside one Qdrant collection."""
from qdrant_client import models
from .common import client, embed_query, COLLECTION

def flt(audience=None, region=None, status=None, product=None):
    must = []
    if audience: must.append(models.FieldCondition(key="audience", match=models.MatchValue(value=audience)))
    if status: must.append(models.FieldCondition(key="status", match=models.MatchValue(value=status)))
    if product: must.append(models.FieldCondition(key="product", match=models.MatchValue(value=product)))
    if region:   # a region's customers see national docs plus their own region's docs
        must.append(models.FieldCondition(key="region", match=models.MatchAny(any=["ALL", region])))
    return models.Filter(must=must) if must else None

def keyword(q, k=5, f=None, coll=COLLECTION):
    """BM25 over the full-text index on the 'text' payload field."""
    return client().query_points(coll, query=models.TextQuery(text=q), using="text", query_filter=f,
                                 limit=k, with_payload=True).points

def semantic(q, k=5, f=None, coll=COLLECTION, params=None):
    """Nearest neighbours of the query embedding (HNSW index)."""
    return client().query_points(coll, query=embed_query(q).tolist(), using="dense", query_filter=f,
                                 search_params=params, limit=k, with_payload=True).points

def hybrid(q, k=5, f=None, coll=COLLECTION, depth=20):
    """Run both, then fuse the two ranked lists with Reciprocal Rank Fusion inside Qdrant."""
    return client().query_points(coll, prefetch=[
        models.Prefetch(query=models.TextQuery(text=q), using="text", filter=f, limit=depth),
        models.Prefetch(query=embed_query(q).tolist(), using="dense", filter=f, limit=depth)],
        query=models.RrfQuery(rrf=models.Rrf()), limit=k, with_payload=True).points
