"""Ticket corpus (40k synthetic support messages) + 200 held-out query messages for index benchmarks."""
import os, json, random
import numpy as np
from .common import ROOT, embed
def tickets():
    return [json.loads(l) for l in open(os.path.join(ROOT, "data", "tickets.jsonl"))]
def held_out(n=200):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mt", os.path.join(ROOT, "data", "make_tickets.py")); mt = importlib.util.module_from_spec(spec); spec.loader.exec_module(mt)
    have = {t["text"] for t in tickets()}; random.seed(99); out = []
    for r in mt.make(4000):
        if r["text"] not in have: out.append(r["text"])
        if len(out) == n: break
    return out
def vectors():
    T = tickets(); return T, embed([t["text"] for t in T])
def query_vectors():
    Q = held_out(); return Q, embed(Q, kind="passage")   # held-out messages are searched like new tickets ("find similar tickets")
def exact_topk(X, Qv, k=10):
    s = Qv @ X.T; return np.argsort(-s, axis=1)[:, :k]          # vectors are unit length: dot = cosine
