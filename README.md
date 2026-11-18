# Data for AI

Hands-on tutorials that go with the **Data for AI** videos on Microsoft Fabric and open data standards. Each folder is one video. You can follow the written steps, regenerate the sample data, and run the same Kusto Query Language (KQL) in your own workspace.

The lessons are built in an existing Fabric workspace that runs on a Fabric capacity. Item names in the steps (`IoTEventhouse`, `Telemetry`, `SensorReadings`) match the video so the two stay in sync.

## Videos

| # | Title | Folder | Video |
| --- | --- | --- | --- |
| 1 | Create an Eventhouse and ingest data | [01-eventhouse-create-and-ingest](01-eventhouse-create-and-ingest/) | [Watch](https://youtu.be/4E5-xwSKkG0) |
| 2 | Tables and materialized views | [02-tables-and-materialized-views](02-tables-and-materialized-views/) | [Watch](https://youtu.be/YYVZEckY2gY) |
| 3 | Ontology with Apache Ossie (incubating) | [03-ontology-with-apache-ossie](03-ontology-with-apache-ossie/) | [Watch on YouTube](https://youtu.be/TV70PHBNNPk) |

## How to use this repo

1. Open the folder for the video you are on and read its README.
2. Recreate the same items in your own Microsoft Fabric workspace. A Fabric-enabled capacity is required.
3. Upload or regenerate the sample data, then run the KQL files in the default queryset.

Folder 03 runs locally with Python and SQLite; its README lists what to install.

Do not put passwords, connection strings, workspace or tenant identifiers, or other private details into this repo.

## Prerequisites

For the Fabric videos (1 and 2):

- A Microsoft Fabric workspace on a Fabric-enabled capacity
- Permission to create items in that workspace

## Official starting points

- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Get started with Real-Time Intelligence](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-started-with-real-time-intelligence)
