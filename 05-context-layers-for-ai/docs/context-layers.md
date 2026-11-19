# Context layers: the concepts

A short, vendor-neutral summary of the ideas in video 5.

## Five related terms

| Term | What it is | Answers |
|---|---|---|
| Semantics | The meaning of a term, number or column | What does this mean? |
| Ontology | A formal model of concepts, relationships and rules | What exists, and how is it related? |
| Semantic layer | A governed business view: metrics, definitions, access | What is the official number? |
| Knowledge graph | Real things and their links, shaped by an ontology | How is this thing connected? |
| Context layer | All of the above, linked and kept current for AI | What does an agent need right now? |

## Why agents need context

An agent that only sees table names has to guess: what counts as an alert, which metric is official, who may see personal data, and what happened recently that changes the answer. Language models know language; they do not know an organization's definitions, rules or history.

## Semantic layer plus knowledge graph

- The **semantic layer** contributes business semantics (terms, certified metrics) and governance (access, certification, freshness).
- The **knowledge graph** contributes ontological modeling: concepts, relationships, rules, and real instances linked to those concepts.
- A **context layer** combines both in one linked model that represents what the organization knows across data, metadata, business concepts, policies and processes.

## A living model

A context layer keeps adding **runtime context**: events (a test starts), decisions (exclude its readings), actions (dispatch a technician) and outcomes (a fan is replaced). Each record links to what it is about. Agent answers are written back with their evidence, so the next question starts from what already happened.

## Neural plus symbolic

The neural side (a language model) is good at patterns: reading the question, matching words to concepts, writing the reply. The symbolic side is exact: ontology rules, policies and certified metrics, checked in code. The neural side proposes; the symbolic side decides what is allowed and true. The context layer is where they meet.

## How this lesson maps to the ideas

| Idea | In this folder |
|---|---|
| Business semantics | `models/iot.semantic_model.yaml` (Apache Ossie semantic model) |
| Ontology and mapping | `models/iot.ontology.yaml`, `models/iot.mapping.yaml` |
| Linked instances | customers, sites and sensors from `data/iot.duckdb` |
| Governance | `context/policies.yaml` (our own format) |
| Runtime context | `context/runtime_seed.jsonl` → `out/runtime_log.jsonl` (our own format) |
| One linked graph | `context_layer.py build` (networkx) |
| Context assembler | `context_layer.py ask` (teaching code) |
