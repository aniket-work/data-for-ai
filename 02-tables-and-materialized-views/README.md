# Video 2 — Create tables and materialized views

**Status: draft.** This lesson is planned to follow video 1. The steps and KQL below are a starting point and may change when the video is recorded.

We stay in the same Fabric workspace and the `IoTEventhouse` Eventhouse from [video 1](../01-eventhouse-create-and-ingest/). The `Telemetry` table is already loaded. In this lesson you will see how to create a table with a command, then add materialized views on top of that data.

## Planned steps

1. Recap the Eventhouse, the default KQL database, and the `Telemetry` table from video 1.
2. Create a table with `.create table`, and compare that with the table the Get data wizard created for you.
3. Explain when to use an **update policy** vs a **materialized view** (aggregations belong in a materialized view).
4. Create a **latest-reading** materialized view with `arg_max`, so each device has one current row.
5. Create an **hourly average by Site** materialized view with `bin(Timestamp, 1h)`.
6. Use `backfill=true` and `async` so both views include the 6,000 rows already in `Telemetry`.
7. Query the views and compare them with the same aggregations run directly on `Telemetry`.

## Draft KQL

All statements below are **draft**. Do not treat them as the final script until video 2 is recorded. Run them in the default queryset for `IoTEventhouse`.

```kusto
// DRAFT — video 2
// Example of creating a table with a command.
// Telemetry already exists from video 1, so this is here as a pattern,
// not something you must run against the same database a second time.
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

```kusto
// DRAFT — video 2
// Latest reading per device. arg_max keeps the row with the most recent Timestamp.
// backfill=true includes rows already in Telemetry. The create must be async.
.create async materialized-view with (backfill=true) TelemetryLatest on table Telemetry
{
    Telemetry
    | summarize arg_max(Timestamp, *) by DeviceId
}
```

```kusto
// DRAFT — video 2
// Hourly average measurements by Site, including a backfill of existing data.
.create async materialized-view with (backfill=true) TelemetryHourlyAvgBySite on table Telemetry
{
    Telemetry
    | summarize
        AvgTemperature = avg(Temperature),
        AvgHumidity = avg(Humidity),
        AvgPressure = avg(Pressure),
        EventCount = count()
        by Site, bin(Timestamp, 1h)
}
```

A copy of these drafts is in [kql/02_materialized_views.draft.kql](kql/02_materialized_views.draft.kql).

## Official docs

- [.create table command](https://learn.microsoft.com/en-us/kusto/management/create-table-command?view=microsoft-fabric)
- [Create and edit materialized views](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/materialized-view)
- [Create materialized view](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-create?view=microsoft-fabric)
- [Materialized views use cases](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-use-cases?view=microsoft-fabric)
