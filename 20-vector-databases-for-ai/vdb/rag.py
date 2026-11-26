"""Retrieval-augmented generation: hybrid search with filters -> prompt with numbered sources -> local LLM."""
import os, time, httpx
from . import search as S
LLM_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8999/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-4b-instruct-2507")
SYSTEM = ("You are Kestrel Bay Bank's customer help assistant. Answer ONLY from the numbered sources. "
          "Cite sources like [KB-101]. If the sources do not contain the answer, say you don't know and suggest contacting the bank. "
          "Be brief: at most 3 sentences.")
NO_RAG_SYSTEM = "You are Kestrel Bay Bank's customer help assistant. Be brief: at most 3 sentences."

def retrieve(q, region=None, k=4):
    return S.hybrid(q, k=k, f=S.flt(audience="customer", status="current", region=region))

def chat(messages, max_tokens=220):
    t0 = time.time()
    r = httpx.post(f"{LLM_URL}/chat/completions", json=dict(model=LLM_MODEL, messages=messages, temperature=0, max_tokens=max_tokens), timeout=600)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"].strip(), time.time() - t0

def answer(q, region=None, use_retrieval=True, k=4):
    if not use_retrieval:
        txt, dt = chat([{"role": "system", "content": NO_RAG_SYSTEM}, {"role": "user", "content": q}]); return txt, [], dt
    pts = retrieve(q, region, k)
    ctx = "\n\n".join(f"[{p.payload['doc_id']}] {p.payload['text']}" for p in pts)
    who = f"The customer lives in the {region} region. " if region else ""
    txt, dt = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Sources:\n{ctx}\n\n{who}Question: {q}"}])
    return txt, pts, dt
