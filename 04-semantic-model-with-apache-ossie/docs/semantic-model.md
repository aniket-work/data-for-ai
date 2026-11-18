# The Apache Ossie (incubating) core semantic model

A short guide to the parts of an Ossie semantic model used in this lesson. Everything here follows the [core specification](https://github.com/apache/ossie/blob/main/core-spec/spec.md) at version `0.3.0.dev0` (unreleased, apache/ossie commit `74a26be`). The specification and [ossie-schema.json](https://github.com/apache/ossie/blob/main/core-spec/ossie-schema.json) are the authority; this page only summarizes them.

## Document

| Property | Required | Meaning |
|---|---|---|
| `version` | Yes | `0.3.0.dev0` |
| `name` | Yes | Unique model name. A mapping document's `semantic_model_ref.name` must equal it |
| `datasets` | Yes | Non-empty list of logical datasets |
| `description` | No | Human-readable text |
| `ai_context` | No | String, or object with `instructions`, `synonyms`, `examples` |
| `relationships` | No | Joins between datasets |
| `metrics` | No | Model-scoped metrics |
| `nonportable_extensions` | No | `vendor_name` + `data` object; carried, never interpreted |

Each document holds one model at the root. The older `semantic_model` array and `custom_extensions` are no longer accepted.

## Dataset

`name` and `source` are required. `primary_key` is a list of field names; `unique_keys` is a list of such lists. `fields`, `metrics`, `description`, `ai_context` and `nonportable_extensions` are optional.

## Field

`name` and `expression` are required. `expression` has a top-level `sql` (portable `OSSIE_SQL_2026`), `dialects` (`dialect` + `expression`), or both; at least one must be present and the top-level `sql` wins. Optional: `datatype`, `dimension` (`is_time`), `label`, `description`, `ai_context`, `nonportable_extensions`. Field expressions are scalar and read the dataset's source columns.

## Relationship

`name`, `from` (many side), `to` (one side), `from_columns` and `to_columns` are required. The column lists hold **field names**, in matching order and of equal length. Optional: `ai_context`, `nonportable_extensions`.

## Metric

`name` and `expression` are required; `description`, `datatype`, `ai_context` and `nonportable_extensions` are optional.

| | Dataset-scoped (`datasets[].metrics`) | Model-scoped (root `metrics`) |
|---|---|---|
| Field references | Unqualified: `temperature_c` | Qualified: `readings.temperature_c` |
| Source columns | `source.pressure` | Not allowed |
| Other metrics | Not allowed | Only `AGG(dataset.metric)`, no `FILTER` |
| Referenced as | `readings.alert_count` | `alert_rate_pct` |

Within a dataset, field names and dataset-scoped metric names share one namespace.

## Name resolution

| Where the name appears | What it refers to |
|---|---|
| Field `expression` | A column of the same dataset's `source` |
| `primary_key`, `unique_keys` | A field of the same dataset |
| `from_columns` / `to_columns` | A field of the `from` / `to` dataset |
| Dataset-scoped metric | Unqualified: a field; `source.column`: a source column |
| Model-scoped metric | `dataset.field`; inside `AGG`: `dataset.metric` |

Not supported in this version: a field that references another field, a metric that references another metric (except `AGG`), and a dataset whose source is another dataset.
