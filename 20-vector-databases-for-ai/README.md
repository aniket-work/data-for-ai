# 20 — Data as Vectors: Vector Databases for AI, Hands-On

AI systems don't search your data by matching words; they search by **meaning**. An embedding model turns each piece of text into a list of numbers, a **vector**, and a **vector database** finds the stored vectors closest to a question's vector, fast, with filters, at scale. In this lesson we turn a fictional bank's policy library into vectors, load it into **[Qdrant](https://github.com/qdrant/qdrant)**, and measure every trade-off live: similarity metrics, HNSW, IVF, quantization, chunking, metadata filters, hybrid search and a small RAG answer with citations. **pgvector** and **DuckDB vss** run on the same vectors for comparison: pgvector HNSW recall@10 0.980 at 0.4 ms, DuckDB vss 1.000 at 1.8 ms, Qdrant 1.000 at 2.1 ms (40,000 vectors).

Everything runs locally on a CPU: Qdrant as a single binary (no Docker), embeddings with FastEmbed, a small open model on a llama.cpp server. No cloud account, no paid API key.

> **Same bank, new data.** Kestrel Bay Bank is the fictional bank from [Lessons 10](../10-metricflow-banking-metrics/), [11](../11-wrenai-semantic-text-to-sql/) and [12](../12-cube-semantic-layer-ai-agent/). This time we use its **unstructured** data: 34 policy and support documents and 40,000 synthetic support tickets.

## The results

All numbers below were measured in the recorded runs (`results/*.json`). Your numbers will differ a little: HNSW graphs are random, and latency depends on your machine.

**Keyword vs vectors vs hybrid** (94 section chunks, 32 labelled questions: 22 in everyday wording, 10 with codes or policy terms):

| Retriever | recall@5, all | everyday wording | codes and terms | recall@1 | MRR@10 |
|---|---|---|---|---|---|
| Keyword (BM25, Qdrant full-text index) | 88% | 82% | 100% | 69% | 0.76 |
| Semantic (bge-small vectors, HNSW) | 91% | 86% | 100% | 72% | 0.80 |
| **Hybrid (both, fused with RRF)** | **94%** | **91%** | 100% | **75%** | **0.82** |

**Approximate nearest neighbour search** (40,000 x 384 ticket vectors, 200 held-out queries, recall@10 against an exact scan, median latency including the HTTP round trip):

| Qdrant setting | recall@10 | p50 | bytes per vector |
|---|---|---|---|
| Exact scan | 1.000 | 4.8 ms | 1,536 |
| HNSW m=16, hnsw_ef=10 | 0.992 | 1.9 ms | 1,536 |
| HNSW m=16, hnsw_ef=40 | 1.000 | 1.8 ms | 1,536 |
| HNSW m=4, hnsw_ef=10 | 0.910 | 2.2 ms | 1,536 |
| + int8 scalar quantization, no rescore | 0.919 | 2.2 ms | 384 |
| + int8, rescore with 2x oversampling | 1.000 | 1.9 ms | 384 |
| + product quantization x16, no rescore | 0.750 | 2.4 ms | 96 |
| + PQ x16, rescore with 2x oversampling | 0.966 | 2.1 ms | 96 |

Rescoring only re-ranks the candidates already fetched, so without oversampling it cannot bring back neighbours the quantized search missed.

**The filter trap** (intent = gic AND region = Prairies: 376 of 40,000 rows, 0.9%; asked for 10):

| Engine | rows returned | recall@10 |
|---|---|---|
| pgvector HNSW, iterative scan off | 0.24 on average | 0.024 |
| pgvector 0.8 HNSW, `hnsw.iterative_scan = relaxed_order` | 10 | 0.962 |
| Qdrant, payload index + query planner | 10 | 1.000 |

**Chunking** (6 questions about a ~1,000-word account agreement; these 6 were written to test chunking): whole document 1/6, fixed 40-word windows 5/6, sections with the title prefixed 6/6.

**Local RAG** (Qwen3-4B-Instruct-2507 Q4_K_M on CPU, temperature 0, 8 questions): **1/8 without retrieval, 7/8 with retrieval**, every answer cited. Even the one "no retrieval" pass is luck: it said "6 months" while claiming the bank has no formal deferral. llama.cpp output is not bit-identical across runs, so a rerun may score the no-retrieval column one point differently. The RAG miss (q2) is a retrieval problem: the retrieved page only points to the fee schedule, and the model correctly said the amount was not in its sources. For a question no document covers (crypto trading) it says "I don't know".

> **Honest notes.** Kestrel Bay Bank, its documents, fees and tickets are fictional. The 40,000 tickets are generated from templates with a fixed seed, so they are easier than real support data. The evaluation sets are small: read differences as a direction, not a law. Latencies are medians on one 8-core CPU machine. Whether PostgreSQL uses the HNSW index for the filtered query depends on its statistics; `pg_duckdb.py` prints the plan it chose and forces the index (`enable_seqscan = off`) for the trap rows.

## What you will build

![Ingest path: policy documents, chunked by section, embedded on the CPU and loaded into one Qdrant collection with a dense HNSW index, a BM25 text index and payload indexes. Query path: the question is embedded with the same model, metadata filters are applied, hybrid search fuses BM25 and vectors with RRF, and the top chunks go to a local LLM that answers with citations](diagrams/vector-rag-architecture.png)

| Piece | Where | What it does |
|---|---|---|
| Policy library | `data/make_kb.py` -> `kb/*.md` | 34 fictional documents with front matter (product, doc_type, audience, region, effective, status): policies, FAQs, two fee schedules (current and superseded), regional relief policies, staff-only notes and a long account agreement |
| Tickets | `data/make_tickets.py` -> `data/tickets.jsonl` | 40,000 unique synthetic support messages (26 intents, 5 regions) for the index benchmarks |
| Questions | `eval/` | 32 retrieval questions, 6 long-document questions, 8 RAG questions with expected answers |
| Shared code | `vdb/common.py`, `vdb/search.py`, `vdb/tickets.py`, `vdb/rag.py` | chunking, embedding (with a cache), the three retrievers, filters, the RAG prompt |
| Collection | `scripts/build_index.py` | `kestrel_policies`: dense vector (cosine, HNSW m=16, ef_construct=100), BM25 full-text index with stemming and stop words, 6 keyword payload indexes |

**Why Qdrant for this lesson.** It runs as one static binary, and every concept in the lesson is a setting in one engine: HNSW parameters, scalar / product / binary quantization with rescoring and oversampling, payload indexes and filter-aware search, a BM25 full-text index, and prefetch + RRF fusion in the Query API. Chroma and LanceDB are good embedded alternatives. Note that the Qdrant Python client's in-process "local mode" is an exact brute-force scan (it ignores HNSW and quantization settings), so the benchmarks here use the real server.

## Prerequisites

- **Python 3.12**, `curl`, about 3.5 GB of disk (Qdrant binary, embedding model, local LLM)
- Linux x86_64 or macOS. `scripts/qdrant_up.sh` downloads the Linux musl build of Qdrant; on macOS or Windows download the matching release from [Qdrant releases](https://github.com/qdrant/qdrant/releases) into `.qdrant/bin/`, or run Qdrant any other way on port 6333.
- For step 6 only: **PostgreSQL 17 with pgvector 0.8** (Debian/Ubuntu: `apt install postgresql-17 postgresql-17-pgvector`). DuckDB's `vss` extension is downloaded automatically.
- For step 7 only: a local OpenAI-compatible model server. The video used [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` with `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (about 2.5 GB) on an 8-core CPU; one answer took about 10 seconds. Ollama, LM Studio or vLLM work too.

## Step by step

### 1. Install

```bash
git clone https://github.com/aniket-work/data-for-ai
cd data-for-ai/20-vector-databases-for-ai
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python data/make_tickets.py           # 40,000 synthetic tickets -> data/tickets.jsonl
```

The policy documents are already in `kb/` (`python data/make_kb.py` regenerates them). The first run downloads `BAAI/bge-small-en-v1.5` (about 65 MB) through FastEmbed.

### 2. Start Qdrant and build the collection

```bash
scripts/qdrant_up.sh                     # downloads Qdrant v1.20.2 once into .qdrant/, starts it on :6333
python scripts/build_index.py --fresh    # 94 chunks from 34 documents, embedded on the CPU
```

Stop Qdrant with `pkill -f .qdrant/bin/qdrant`. Data lives in `.qdrant/storage` (git-ignored).

### 3. Vectors, metrics and search

```bash
python scripts/vectors.py                # four sentences -> 384 numbers each, cosine / dot / euclidean
python scripts/show_query.py "I'm relocating from Ontario to BC, do I need a new account?" KB-117
python scripts/compare.py --misses       # keyword vs semantic vs hybrid on the 32 questions
python scripts/map.py                    # results/embedding_map.png (PCA and t-SNE); --show opens it with feh
python scripts/metrics.py                # cosine, dot, euclidean and manhattan collections, compared
python scripts/chunking.py               # whole document vs fixed windows vs sections
```

### 4. Indexes and quantization

```bash
python scripts/ann_bench.py              # first run embeds the 40,000 tickets (a few minutes on a CPU, then cached)
python scripts/ann_bench.py --rebuild    # rebuild the four collections
```

### 5. Metadata filters

```bash
python scripts/filters.py region         # a Saskatoon customer: national + Prairies documents only
python scripts/filters.py audience       # public chat: staff-only notes excluded
python scripts/filters.py status         # current fee schedule only
```

### 6. pgvector and DuckDB on the same vectors

```bash
scripts/pg_up.sh                         # private PostgreSQL cluster in .pg/ (socket /tmp/kbank_pg, port 55432)
python scripts/pg_duckdb.py              # exact, HNSW and IVFFlat in pgvector; HNSW in DuckDB vss; the filter trap
```

`pg_up.sh` looks for the PostgreSQL binaries in `/usr/lib/postgresql/17/bin`; set `PG_BIN` if yours are elsewhere. Stop the cluster with `pg_ctl -D .pg stop`. If DuckDB cannot download `vss` over plain HTTP on your network, the script fetches it over HTTPS and installs it from the file.

### 7. Local RAG

```bash
LLAMA_SERVER=/path/to/llama-server MODEL=/path/to/Qwen3-4B-Instruct-2507-Q4_K_M.gguf bash scripts/start_local_llm.sh
```

```bash
python scripts/rag.py "We had to evacuate because of the wildfire. Can I skip my mortgage payments?" --region Prairies
python scripts/rag.py "We had to evacuate because of the wildfire. Can I skip my mortgage payments?" --no-retrieval
python scripts/rag_eval.py               # 8 questions, with and without retrieval -> results/rag_eval.json
```

`rag.py` reads `LLM_BASE_URL` (default `http://127.0.0.1:8999/v1`) and `LLM_MODEL` (default `qwen3-4b-instruct-2507`); point them at any OpenAI-compatible server to try another model.

## Try next

- Swap in a bigger embedding model in `vdb/common.py` (and rebuild with `--fresh`): does everyday-wording recall go up?
- Add your own questions to `eval/queries.jsonl` and rerun `compare.py`.
- Try binary quantization in `ann_bench.py`, and different oversampling factors.
- Change the RRF constant or weights in `vdb/search.py` (`models.Rrf(k=..., weights=[...])`).

## Files

| File | What it is |
|---|---|
| `data/make_kb.py`, `kb/` | The policy library generator and its 34 documents |
| `data/make_tickets.py` | 40,000 synthetic tickets (fixed seed) |
| `eval/queries.jsonl`, `eval/long_doc_queries.jsonl`, `eval/rag_questions.jsonl` | Retrieval, chunking and RAG questions with answers |
| `vdb/` | Shared code: chunking, embeddings, retrievers, filters, RAG prompt |
| `scripts/qdrant_up.sh`, `scripts/pg_up.sh`, `scripts/start_local_llm.sh` | Start Qdrant, a private PostgreSQL, the local model |
| `scripts/build_index.py`, `compare.py`, `show_query.py`, `vectors.py`, `metrics.py`, `chunking.py`, `map.py`, `ann_bench.py`, `filters.py`, `pg_duckdb.py`, `rag.py`, `rag_eval.py`, `show.py` | The demos from the video |
| `results/` | Results from the recorded runs |
| `diagrams/` | archify diagram (PNG, SVG, interactive HTML, archify JSON) |
| `docs/slides.pdf` | Slides from the video |

## Credits and licences

The documents, questions, tickets and scripts were written for this lesson as teaching code. [Qdrant](https://github.com/qdrant/qdrant) (Apache-2.0), [qdrant-client](https://github.com/qdrant/qdrant-client) and [FastEmbed](https://github.com/qdrant/fastembed) (Apache-2.0), [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) (MIT), [pgvector](https://github.com/pgvector/pgvector) (PostgreSQL License), [DuckDB](https://duckdb.org) and [duckdb-vss](https://github.com/duckdb/duckdb-vss) (MIT), [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT), [Qwen3](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) (Apache-2.0), [rich](https://github.com/Textualize/rich) (MIT), scikit-learn (BSD-3) and matplotlib are the work of their authors.

Further reading: Malkov and Yashunin, *HNSW* (arXiv:1603.09320); Jégou, Douze and Schmid, *Product quantization for nearest neighbor search* (TPAMI 2011); Douze et al., *The Faiss library* (arXiv:2401.08281); Cormack, Clarke and Büttcher, *Reciprocal Rank Fusion* (SIGIR 2009); Robertson and Zaragoza, *BM25 and beyond* (2009); Lewis et al., *Retrieval-Augmented Generation* (arXiv:2005.11401); Xiao et al., *C-Pack / BGE* (arXiv:2309.07597); Muennighoff et al., *MTEB* (arXiv:2210.07316).
