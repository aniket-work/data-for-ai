# 16 · Context Graphs for AI Agents: Decision Traces Your Agent Can Query

> Lesson 16 of **Data for AI**. Video: coming soon. Everything here is fictional and runs locally, no API keys.

A **context graph** links the entities of a business (products, lots, shipments, carriers) with the **decision traces** around them: what triggered each decision, which policy version applied, what evidence was used, who proposed and approved it, which precedents it cited, what happened afterwards, and whether it was later overturned. An AI agent queries the graph for context before it decides, and writes its own decision back as a new trace for a human to approve.

In this lesson we build one for **Kestrel Cold Chain**, a fictional vaccine and biologics distributor, and ask the same local model five questions twice: once with plain RAG over the same facts written as documents, and once with the context graph.

| Q | Question | Correct | The trap |
| --- | --- | --- | --- |
| 1 | SH-2051 logged 14 min at 9.6 C | RELEASE | SOP v3 is in force, v2 was superseded |
| 2 | SH-2057 froze. Release it like SH-1990? | DESTROY | the SH-1990 release (DEC-118) was overturned by DEC-121 |
| 3 | SH-2060 logged 22 min at 10.1 C | QUARANTINE | lot L-A-04 has only 35 of 100 budget minutes left (multi-hop) |
| 4 | SH-2063 on Frostline, 8 min at 8.4 C | ESCALATE | DEC-140 put the carrier on probation until 2026-12-31 |
| 5 | Why was SH-1975 released? | EXPLAIN | cite the real trace (DEC-131), not a similar memo |

**Result** (Qwen2.5-7B-Instruct Q4_K_M on llama.cpp, CPU, temperature 0): plain RAG **1/5**, context graph **5/5**. RAG relied on a superseded policy or an overturned decision twice, the graph never did. The saved runs in `runs/` are the ones shown in the video.

## Files

| Path | What it is |
| --- | --- |
| `build_data.py` | Writes the sample tables to `data/` (one CSV per node type, plus decisions and outcomes) and the same facts as wiki pages and memos to `docs_corpus/` |
| `cg.py` | The lesson: build the graph (NetworkX), inspect it, the graph retriever, the plain RAG baseline (BM25), the LLM call, grading, write-back and export |
| `questions.yaml` | The five questions with expected answers |
| `gql/context_queries.gql` | The same lookups written in GQL for graph in Microsoft Fabric (not executed here) |
| `runs/` | Saved answers from the video |
| `diagrams/` | The agent loop and the Fabric mapping (JSON, HTML, PNG, SVG) |
| `docs/slides.pdf` | Slides from the video |

## Run it

```bash
pip install -r requirements.txt
python build_data.py
python cg.py build            # 125 nodes, 340 edges
python cg.py stats
python cg.py show SH-2057
python cg.py trace DEC-131

# any OpenAI-compatible endpoint; the video used llama.cpp on CPU
llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf --alias qwen2.5-7b-instruct --port 8089 -c 8192 --temp 0 --seed 42

python cg.py context 3        # what the graph retriever gives the model
python cg.py ask 2 --mode rag
python cg.py ask 2 --mode graph
python cg.py ask 5 --mode graph
python cg.py compare
python cg.py scorecard
python cg.py writeback 2      # the agent's decision becomes a new, proposed trace
python cg.py export           # node and edge tables for a Fabric graph model
```

Set `LLM_BASE_URL` and `LLM_MODEL` to use another endpoint. `python cg.py ask N --cached` replays a saved run without a model.

## How the graph retriever works

For a shipment question, `graph_context()` runs a few graph queries and hands the model a short context pack with node IDs:

1. Resolve the shipment, lot, product, carrier and excursion from the question.
2. **Policy in force** on the excursion date, following `SUPERSEDES`.
3. **Lot budget**: sum the minutes deducted by final decisions triggered by earlier excursions on the same lot.
4. **Precedents**: past decisions on the same kind of excursion, with `OVERTURNED by` flags and outcomes.
5. **Active constraints** (`CONSTRAINS` edges with a `valid_to` date) on the carrier, lot, product or site.
6. The policy's checks answered from the graph (froze? within limits? enough budget?).

The model decides and cites IDs. `writeback` stores the result as a `Decision` node with `status: proposed`, linked with `TRIGGERED_BY`, `APPLIED`, `CITES`, `CONSIDERED` and `PROPOSED_BY` edges. Under `POL-SIGNOFF-01`, a human QA reviewer approves before stock moves.

## Context graph vs knowledge graph vs RAG

| | Plain RAG | Knowledge graph | Context graph |
| --- | --- | --- | --- |
| Stores | text chunks | entities and facts | facts, decisions, evidence, outcomes |
| Knows current vs superseded | no | partly | yes (`SUPERSEDES`, validity dates) |
| Knows a decision was reversed | no | no | yes (`OVERTURNS`) |
| Answers "why?" | guesses from similar text | what, not why | the trace, with IDs |

## Taking it to Microsoft Fabric

- [Graph in Microsoft Fabric](https://learn.microsoft.com/fabric/graph/overview) (preview) builds a labeled property graph over OneLake tables and is queried with GQL (ISO/IEC 39075). `python cg.py export` writes one CSV per node type and per edge type to `data/fabric/`, the shape you map in a graph model ([how graph works](https://learn.microsoft.com/fabric/graph/how-graph-works)).
- `gql/context_queries.gql` holds the lookups as GQL. They are not executed in this lesson; check them against the [GQL quick reference](https://learn.microsoft.com/fabric/graph/gql-reference-abridged) and [current limitations](https://learn.microsoft.com/fabric/graph/limitations).
- A Fabric data agent can use a graph as a data source (natural language to GQL, preview), and the [ontology item in Fabric IQ](https://learn.microsoft.com/fabric/iq/ontology/overview) (preview) defines shared business terms bound to your data.
- The decision log is the part you capture yourself: write traces when decisions are made and land them as tables next to your entities.

## Honest notes

- The answers come from a real open-weights model on CPU. Small models are not perfectly repeatable, so your runs may differ slightly from the saved ones. In the video the model's waiting time is cut.
- The graph retriever computes the policy checks; the model combines them with precedents and constraints, decides and cites. Plain RAG gets the same model, prompt rules and facts, only as retrieved documents.
- RAG's one correct answer (Q1) was partly luck: it read the lot budget as 100 minutes instead of 95.
- The company, products, lots, people (role IDs only) and numbers are invented. The policy formats are teaching formats written for this lesson, not a standard.
