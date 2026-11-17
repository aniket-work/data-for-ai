# Eventhouse concepts

Short, plain-language notes that go with video 1. Every fact below is taken from Microsoft Learn. Preview features are labeled.

## Eventhouse vs KQL database

An **Eventhouse** is a container for real-time, time-based data. It can hold several KQL databases and share compute, storage, and monitoring across them. Use it when the data is event-like: telemetry, logs, IoT and time series, security or compliance logs, or financial records.

A **KQL database** lives inside an Eventhouse. That is where tables, functions, and materialized views sit, and where you run Kusto Query Language (KQL). One workspace can have several Eventhouses. One Eventhouse can have several KQL databases. One database can have several tables.

When you create an Eventhouse, Fabric also creates a **default child KQL database with the same name**. You can rename the database later, and you can add more databases to the same Eventhouse.

Sources:

- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Create an eventhouse](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-eventhouse)
- [Create a KQL database](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-database)

## The default queryset

When a KQL database is created, the portal also creates an attached query environment, listed as `<database-name>_queryset` in the database tree. That is the default queryset: a workbench for running KQL, reviewing results, and running some management commands. You can rename it, and you can also create extra standalone querysets in the workspace.

Sources:

- [Create a KQL database](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-database)
- [Create a KQL queryset](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-query-set)

## Compute and storage, in brief

Eventhouse compute is fully managed and autoscale. After idle time, Fabric can pause the Eventhouse to save cost. Waking it up can take a few seconds. Microsoft Learn also notes that analytics compute is typically available within 5 to 10 seconds.

If a workload cannot wait for that wake-up time, **Capacity Planner** can keep the Eventhouse active. You can also set a 7-day schedule, in 60-minute blocks, with a minimum capacity per block. If no minimum is set, the default minimum is 2 capacity units (about 25 GB of premium cache). Autoscale can still go higher than the minimum.

Storage is billed separately from capacity units and has two tiers:

- **OneLake Cache Storage** — premium storage used for faster queries. The cache policy controls how long recent data stays here.
- **OneLake Standard Storage** — durable storage for all queryable data. The retention policy controls how long data is kept.

When a scheduled minimum capacity is configured, cache storage is included in the capacity charges rather than billed on its own.

Sources:

- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Eventhouse and KQL Database consumption](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/real-time-intelligence-consumption)
- [Schedule Eventhouse capacity](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse-smart-capacity-control)

## OneLake availability

You can turn on **OneLake availability** at the database or the table level. That creates a logical copy of the KQL data in Delta Lake format, which other Fabric engines can query — for example Power BI Direct Lake, a Warehouse, a Lakehouse, or a notebook. There is no extra storage charge for turning this on. Retention on the KQL database also applies to the OneLake copy.

The write into OneLake is batched. By default, Fabric may wait up to three hours, or until files are a healthy size, so it does not write lots of tiny Parquet files. You can lower that delay if you need the copy sooner.

The **SQL analytics endpoint** on an Eventhouse or KQL database appears only when OneLake availability and schema synchronization are both enabled.

Video 1 does not turn OneLake availability on. It is called out here so you know why the option exists.

Source: [Turn on OneLake availability for an eventhouse](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-house-onelake-availability)

## When to use an Eventhouse

Choose an Eventhouse when you are storing and analyzing event-based, time-based data and you want low-latency KQL over that data. It handles structured data, semistructured data such as JSON or XML, and unstructured text. If the work is mostly batch tables and relational reporting, a Lakehouse or Warehouse may be a better fit. If the work is a live stream of events you need to query in near real time, start with an Eventhouse.

Source: [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)

## Ingestion options

The built-in **Get data** wizard is the easiest way to land data in a table. The table below compares the options you are most likely to meet. Other sources can be reached with **Connect more data sources**, which routes through Real-Time hub and Eventstream.

| Option | What it is for | One-time or continuous | Notes | Source |
| --- | --- | --- | --- | --- |
| Local file | Upload a file from your computer | One-time | Used in video 1. Up to 1,000 files, each up to 1 GB uncompressed. The wizard infers schema and can use the first row as headers. | [Get data from file](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-local-file) |
| OneLake or Lakehouse | Read files or tables already in OneLake | One-time through Get data; Lakehouse shortcuts and pipelines are also common later | Useful once the data already lives in Fabric. | [Get data from OneLake](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-onelake) |
| Data pipeline (Data Factory copy) or dataflow | Move or transform data from other Fabric or external sources | Usually scheduled or triggered | Good for repeatable batch loads. | [Data ingestion options in Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/get-data) |
| Eventstream | Stream events into a table, optionally with no-code processing first | Continuous | Direct ingestion, or process the stream first, then land in the Eventhouse. | [Get data from Eventstream](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-eventstream), [Add an Eventhouse destination](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-destination-kql-database) |
| Azure Storage | Ingest from ADLS Gen2 or blob containers | One-time, or continuous | **Continuous ingestion is preview.** The Eventhouse is notified on `BlobCreated` and `BlobRenamed`. A continuous stream can affect billing. | [Get data from Azure Storage](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-azure-storage) |
| Azure Event Hubs | Ingest an existing event hub | Continuous | You can connect through Get data, or add Event Hubs as an Eventstream source and then destination the Eventhouse. | [Get data from Azure Event Hubs](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-event-hub) |
| Amazon S3 | Ingest objects from S3 | One-time or as configured in the wizard | Listed as a Get data source alongside Azure Storage. | [Get data overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-overview) |
| Real-Time hub and other connectors | Sources that are not in the Get data list | Usually continuous, via Eventstream | Choose **Connect more data sources** in the wizard. | [Get data overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-overview) |

**Large message support is preview.** In Get data from an Eventstream or a local file, you can allow `string` or `dynamic` cell values larger than 1 MB, up to 32 MB. For most telemetry, leaving this off and keeping a structured schema is the better default.

Source: [Get data overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-overview)

## The ingestion mapping the wizard creates

In video 1 the Get data wizard created a mapping named **`Telemetry_mapping`** alongside the new `Telemetry` table. You can see it in the mapping drop-down on the **Inspect** step and as **Create mapping (Telemetry_mapping)** on the summary page.

An ingestion mapping tells the engine how to map fields in the incoming data (here, CSV columns) to columns in the table. The wizard creates one for you, so a first load needs no mapping code. You can list a table's mappings later with `.show table Telemetry ingestion csv mappings`.

Sources:

- [Get data from file](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-data-local-file)
- [Data mappings](https://learn.microsoft.com/en-us/kusto/management/mappings?view=microsoft-fabric)
- [.show ingestion mapping command](https://learn.microsoft.com/en-us/kusto/management/show-ingestion-mapping-command?view=microsoft-fabric)

## Looking ahead to video 2

These ideas are used in the next lesson. They are here so the first video can stay focused on create-and-ingest.

### Create a table with a command

The Get data wizard can create a table for you, which is what video 1 does. You can also create an empty table yourself:

```kusto
.create table Telemetry (
    Timestamp: datetime,
    DeviceId: string,
    Site: string,
    Temperature: real,
    Humidity: real,
    Pressure: real,
    Status: string
)
```

Source: [.create table command](https://learn.microsoft.com/en-us/kusto/management/create-table-command?view=microsoft-fabric)

### Update policies vs materialized views

An **update policy** runs as part of ingestion. It is a good fit for reshaping or enriching each incoming batch, for example with a lookup to a dimension table. It cannot aggregate across many ingestion batches, because each run only sees the current batch. Source rows are not queryable until the policy finishes.

A **materialized view** is an aggregation query, a single `summarize`, maintained in the background after ingestion. Use it when you want a rolling aggregate, a latest-row-per-entity view, or a coarser time grain. Source rows are queryable as soon as they are ingested, even before the view has caught up.

If you need an aggregation, use a materialized view, not an update policy.

Source: [Materialized views use cases](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-use-cases?view=microsoft-fabric)

### Create a materialized view, `arg_max`, `bin`, and backfill

```kusto
.create [async] materialized-view [with (PropertyName=PropertyValue, ...)] ViewName on table SourceTable
{
    Query
}
```

Common patterns:

- **Dedup or "latest row"**: `summarize arg_max(Timestamp, *) by DeviceId` keeps the most recent row per device.
- **Time-grain aggregation**: `summarize avg(Temperature) by Site, bin(Timestamp, 1h)` stores hourly averages.
- **backfill**: `backfill=true` builds the view from data already in the source table. That create command must be `async`, the view is not queryable until backfill finishes, and you can optionally limit the window with `effectiveDateTime`. The default, `backfill=false`, starts empty and only includes rows ingested after the view is created.

Sources:

- [Create and edit materialized views](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/materialized-view)
- [Create materialized view](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-create?view=microsoft-fabric)
