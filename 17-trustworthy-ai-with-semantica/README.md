# 17 · Trustworthy AI with Semantica: Every Fact Cited, Every Decision Replayable

> Lesson 17 of **Data for AI**. Video: coming soon. Everything here is fictional and runs locally, no API keys.

An AI agent that sounds confident is not the same as an accountable one. When an auditor asks *why* a claim was fast-tracked, you need four answers: **where each fact came from**, **whether the sources disagreed**, **which rule version was in force on that date**, and **a record of the decision that cannot be quietly edited**.

In this lesson we build that structure around a local LLM with [Semantica](https://github.com/semantica-agi/semantica) (0.7.0, MIT), an open source semantic and provenance layer for Python. The use case is **Cedarline Home Insurance**, a fictional insurer triaging five water-damage claims on 2026-10-20. The same local model routes each claim twice: once with plain RAG over the documents, once with a Semantica evidence pack, a rules check and a guardrail.

| Claim | What happened | Correct route | The trap |
| --- | --- | --- | --- |
| CLM-2601 | kitchen supply line burst, $7,850 | FAST_TRACK | none (control case) |
| CLM-2602 | sewer backup on 2026-08-19, $9,400 | FAST_TRACK | the 2025 wording excluded sewer backup; the 2026 wording (from 2026-06-01) covers it up to $25,000 |
| CLM-2603 | vanity leak, $6,300 | REFER_ADJUSTER | the call says 2026-08-28, the invoice says about 2026-07-25, before the policy started on 2026-08-01 |
| CLM-2604 | laundry room pipe, $18,700 | REFER_ADJUSTER | the call says sudden burst, the adjuster found gradual seepage |
| CLM-2605 | dishwasher hose, $14,600 | STANDARD_REVIEW | guideline v3 (from 2026-09-01) lowered the fast-track limit from $25,000 to $10,000 |

**Result** (Qwen2.5-7B-Instruct Q4_K_M on llama.cpp, CPU, temperature 0, seed 42), 3 points per claim (right route, valid citations, conflicts flagged exactly):

| Context | Right route | Valid citations | Conflicts | Total | Audit record |
| --- | --- | --- | --- | --- | --- |
| Plain RAG | 1 / 5 | 3 / 5 | 3 / 5 | **7 / 15** | none |
| Semantica-backed | 5 / 5 | 5 / 5 | 5 / 5 | **15 / 15** | 5 / 5 |

Plain RAG cited the superseded 2025 wording twice, fast-tracked the claim whose loss happened before the policy started, missed one conflict and garbled another. The saved runs in `runs/` are the ones shown in the video.

## Files

| Path | What it is |
| --- | --- |
| `build_data.py` | Writes the 15 sample documents to `docs_corpus/` (policy wording 2025 and 2026, triage guideline v2 and v3, call notes, adjuster reports, an invoice) and the tables in `data/` (`sources.csv` with credibility and validity windows, `policies.csv`, `facts.csv` with a quote for every fact) |
| `trust.py` | The lesson: provenance store, conflicts, policy versions, rules, plain RAG baseline (TF-IDF), the LLM call, guardrail, grading, audit replay, tamper test and export |
| `runs/` | Saved answers, scorecard and the provenance store from the video |
| `diagrams/` | The agent loop and the Fabric mapping (archify JSON, HTML, PNG) |
| `docs/slides.pdf` | Slides from the video |

## Run it

```bash
pip install -r requirements.txt
python build_data.py
python trust.py build              # provenance store + context graph + policy versions
python trust.py facts CLM-2603     # every fact with source, section, quote and checksum
python trust.py conflicts          # ConflictDetector over all claims
python trust.py rules CLM-2602     # Reasoner: route + plain-English explanation

# any OpenAI-compatible endpoint; the video used llama.cpp on CPU
llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf --port 8089 -c 8192 --seed 42

python trust.py ask 3 --mode rag
python trust.py ask 3 --mode semantica   # writes a hash-chained decision record
python trust.py audit CLM-2603           # replay it: lineage, chain check, prompt hash
python trust.py tamper                   # edit a copy of the store and see what is caught
python trust.py compare
python trust.py scorecard
python trust.py export                   # PROV-O Turtle + flat CSV tables
```

Set `LLM_BASE` (default `http://127.0.0.1:8089/v1`) and `LLM_MODEL` to use another endpoint.

No model? The saved runs from the video work as they are: skip `build` and run `python trust.py scorecard`, `compare`, `audit CLM-2603` and `tamper`. Note that `build` starts from scratch and deletes the saved runs, so run all ten `ask` commands again afterwards.

## What Semantica does here

| Need | Semantica piece | In `trust.py` |
| --- | --- | --- |
| Where did each fact come from? | `ProvenanceManager` (SQLite, W3C PROV-O) | every fact is tracked with its document, section, exact quote, confidence and agent; `verify_chain`, `trace_lineage`, `export_prov` |
| Did the sources disagree? | `ConflictDetector`, `ConflictResolver` | value conflicts per claim and property; strategies such as `highest_confidence`, `credibility_weighted`, `most_recent`, `voting`, `expert_review` |
| Which version was in force? | `ContextGraph` validity windows, `PolicyEngine` history | clauses are picked at the date of loss, the guideline at the triage date; GL-TRIAGE v2 to v3 is a recorded policy update |
| Which rule applied? | `Reasoner` + `ExplanationGenerator` | IF ... THEN rules, forward chaining, a plain-English explanation |
| Can we replay the decision? | `record_decision`, `record_policy_application`, provenance entity `DEC-<claim>-<prompt hash>` | `audit` shows the evidence, rule, model output, guardrail result and chain check |

## How a decision is made

1. **Gather**: the facts for the claim, each with document, section and quote.
2. **Check**: conflicts between sources, the clause in force at the date of loss, the guideline in force today, and the rule route with its explanation.
3. **Decide**: the local LLM gets this evidence pack and returns a route, citations and the conflicts it sees.
4. **Guardrail**: if the model's route differs from the rule route, the final route is `REFER_ADJUSTER`, so a human decides.
5. **Record**: the decision is stored in the context graph, the policy engine and the provenance chain with a hash of the exact prompt.

Plain RAG mode gives the same model the claim's own documents plus the top 4 TF-IDF chunks from the wording and guidelines, with no versions, no conflict check and no record.

## Honest notes

- The **route comes from deterministic rules**. The model explains and cites; the guardrail makes sure it agrees with the rules or hands the claim to a person. That is the point: accountability comes from structure, not from a bigger model.
- In Semantica 0.7.0 the provenance **checksum covers who, which activity, when, the source and the lineage, not the extracted value, quote or metadata**. `trust.py tamper` shows both cases: re-attributing a fact breaks the checksum, while editing a value does not. That is why `trust.py` adds a **grounding check** (the quote must appear in the source document, and the numbers and dates must match the quote).
- Semantica explains what is outside the model (context, sources, rules, trail), not the model's internal reasoning.
- Grading: a citation is valid if it exists in the provenance store and was in force (guidelines judged at the triage date, wording at the date of loss). Conflicts must match the expected set exactly.
- The company, people, claims and documents are fictional.

## Microsoft Fabric

Fabric's lineage view is **item level** (which pipeline, lakehouse or report feeds which, inside a workspace), with impact analysis downstream. Semantica adds **fact level** provenance: which sentence fed which decision. `trust.py export` writes `export/provenance.ttl` (PROV-O Turtle) plus `export/provenance_entries.csv` and `export/lineage_edges.csv`; upload the CSVs to a lakehouse and use **Load to Tables** to get Delta tables you can query from the SQL analytics endpoint. This step was not run against a Fabric capacity in this lesson.

Purview's data governance features are moving into Fabric; Purview's security and compliance features continue. Check Microsoft Learn for the current state:

- [Lineage in Microsoft Fabric](https://learn.microsoft.com/fabric/governance/lineage)
- [Load to Delta tables](https://learn.microsoft.com/fabric/data-engineering/load-to-tables)

## Try it yourself

- Add a sixth claim with its own trap and an expected route.
- Publish guideline v4 with a new limit and watch the policy history.
- Change a source's credibility and see how the conflict resolution changes.
- Run `tamper`, then `audit`, and explain what was caught and why.
