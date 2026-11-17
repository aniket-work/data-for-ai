# Concepts: tables and materialized views

Background for [video 2](../README.md). Every section links to the Microsoft Learn page it is based on.

## Creating a table: Get data vs `.create table`

- The **Get data** wizard reads a sample of your source (a local file, OneLake, a stream, and more), infers a schema, and creates the table and an ingestion mapping for you. That is how `Telemetry` was created in video 1.
- The **`.create table`** management command creates a new, **empty** table with exactly the columns and data types you write: `.create table T (Col1: type, Col2: type, ...)`. Because it is plain text, you can script it, review it, and keep it in source control.
- If a table with the same (case-sensitive) name already exists, `.create table` returns success **without changing** the existing table.
- In the Fabric portal you can also create an empty table from **+ New > Table**. Its **command viewer** shows the commands it will run.

Sources:

- [.create table command](https://learn.microsoft.com/en-us/kusto/management/create-table-command?view=microsoft-fabric)
- [Create an empty table (Fabric)](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-empty-table)
- [Get data overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-overview)

## Ingest from a query: `.set-or-append`

These commands run a query and ingest its result into a table:

| Command | If the table exists | If the table doesn't exist |
| --- | --- | --- |
| `.set` | The command fails | The table is created and data is ingested |
| `.append` | Data is appended | The command fails |
| `.set-or-append` | Data is appended | The table is created and data is ingested |
| `.set-or-replace` | Data replaces the existing data | The table is created and data is ingested |

Good to know:

- Columns are matched by **type and position, not by name**. Keep the query's columns in the same order as the table's.
- It is a **direct ingestion**, so there are no automatic retries.
- Microsoft recommends keeping each ingest-from-query operation under about 1 GB of data.
- The command returns the **extents** (data shards) it created, including each extent's row count.

Source: [Kusto query ingestion (set, append, replace)](https://learn.microsoft.com/en-us/kusto/management/data-ingestion/ingest-from-query?view=microsoft-fabric)

## Why duplicates happen

Devices often keep a local cache and can resend data they already sent. Pipelines and jobs get retried after failures. Duplicates change the result of anything that counts or averages. Microsoft's guidance is to prevent duplication as early in the pipeline as you can. When you can't change the source, handle it in the database, for example with a `take_any` materialized view.

Sources:

- [Handle duplicate data](https://learn.microsoft.com/en-us/kusto/concepts/dealing-with-duplicates?view=microsoft-fabric)
- [Materialized views use cases: deduplicate records](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-use-cases?view=microsoft-fabric)

## What a materialized view is

A materialized view exposes **one aggregation query** (a single `summarize`) over a source table and keeps its result up to date. It has two parts:

- the **materialized part**: a table of records that are already aggregated, with one record per group-by combination;
- the **delta**: newly ingested source records that have not been processed yet.

A background process moves the delta into the materialized part. When you query the view by name, Fabric combines the two, so the result is **always up to date**, and usually faster and cheaper than running the aggregation over the raw table.

Source: [Materialized views overview](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-overview?view=microsoft-fabric)

## Supported aggregations

The view query must end with a single `summarize`. Supported aggregations include `count`, `countif`, `dcount`, `dcountif`, `min`, `max`, `avg`, `avgif`, `sum`, `sumif`, `arg_max`, `arg_min`, `take_any`, `take_anyif`, `hll`, `make_set`, `make_list`, `make_bag`, `percentile`/`percentiles`, and `tdigest`. Common patterns:

- `arg_max(Timestamp, *) by Key`: the latest row per key (our `DeviceLatest`)
- `take_any(*) by Key1, Key2`: one row per key combination, which deduplicates (our `SensorReadingsDedup`)
- `avg(...)`, `count() by Key, bin(Timestamp, 1h)`: a rollup at a lower time resolution (our `SiteHourly`)

A view with only a single `arg_max`, `arg_min`, or `take_any` aggregation can perform better than one that mixes them with other aggregations.

Source: [.create materialized-view](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-create?view=microsoft-fabric)

## Backfill

- `backfill=false` (the default): the view starts empty and only covers records ingested **from now on**. It's available for queries immediately.
- `backfill=true`: the view is also built from the records **already in the source table**. It isn't available for queries until the backfill finishes.
- For backfill, Microsoft Learn says to use the **async** form, `.create async materialized-view with (backfill=true) ...`, and to monitor it with `.show operations`. In the video the source table was tiny (6,500 rows), so the regular command finished in about a second.
- On large tables backfill can take a long time. If the backfill ultimately fails, you re-run the create command.

Source: [.create materialized-view: backfill](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-create?view=microsoft-fabric)

## Materialized views vs update policies

| | Materialized view | Update policy |
| --- | --- | --- |
| When it runs | In the background, after ingestion | During ingestion, for each batch |
| Aggregations | Yes, across all the data | Only within a single ingestion batch |
| Best for | Dedup, latest per key, rollups | Transforming, parsing, enriching rows |

If you need an aggregation, use a materialized view. Update policies are covered in video 3.

Sources:

- [Materialized views vs. update policies](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-use-cases?view=microsoft-fabric)
- [Update policy overview](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric)

## Querying a view: by name vs `materialized_view()`

- `ViewName`: combines the materialized part with the delta. Always the freshest result.
- `materialized_view("ViewName")`: only the materialized part. It may lag slightly, but it is always faster. Microsoft recommends it whenever a little lag is acceptable, for example telemetry dashboards.
- `materialized_view("ViewName", 10m)`: the materialized part if it was materialized in the last 10 minutes, otherwise the full view.

Sources:

- [materialized_view() function](https://learn.microsoft.com/en-us/kusto/query/materialized-view-function?view=microsoft-fabric)
- [Materialized views overview: queries](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-overview?view=microsoft-fabric)

## Health: `.show materialized-views`

`.show materialized-views` lists every view with its definition and state. Useful columns:

- `IsHealthy`: `false` only when at least five materialization attempts in a row have failed **and** `MaterializedTo` is more than an hour old.
- `IsEnabled`: whether materialization is running. A view hit by a permanent error (for example an incompatible source schema change) is disabled automatically.
- `MaterializedTo`: the newest source `ingestion_time()` already processed into the view.
- `LastRun`, `LastRunResult`: when materialization last ran, and `Completed` or `Failed`.

Check `IsHealthy` together with `IsEnabled`. For failures, use `.show materialized-view <name> failures`.

Sources:

- [.show materialized-views](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-show-command?view=microsoft-fabric)
- [Monitor materialized views](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-views-monitoring?view=microsoft-fabric)

## In the Fabric portal

Materialized views appear in the database tree under **Materialized views**. You can also create and edit them from the database's **+ New** menu.

Source: [Create and edit materialized views (Fabric)](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/materialized-view)
