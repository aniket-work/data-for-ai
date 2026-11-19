# Data for AI

Hands-on tutorials that go with the **Data for AI** videos on Microsoft Fabric and open data standards. Each folder is one video. You can follow the written steps, regenerate the sample data, and run the same Kusto Query Language (KQL) in your own workspace.

The lessons are built in an existing Fabric workspace that runs on a Fabric capacity. Item names in the steps (`IoTEventhouse`, `Telemetry`, `SensorReadings`) match the video so the two stay in sync.

## Videos

| # | Title | Folder | Video |
| --- | --- | --- | --- |
| 1 | Create an Eventhouse and ingest data | [01-eventhouse-create-and-ingest](01-eventhouse-create-and-ingest/) | [Watch](https://youtu.be/4E5-xwSKkG0) |
| 2 | Tables and materialized views | [02-tables-and-materialized-views](02-tables-and-materialized-views/) | [Watch](https://youtu.be/YYVZEckY2gY) |
| 3 | Ontology with Apache Ossie (incubating) | [03-ontology-with-apache-ossie](03-ontology-with-apache-ossie/) | [Watch on YouTube](https://youtu.be/TV70PHBNNPk) |
| 4 | Semantic model in Apache Ossie (incubating) | [04-semantic-model-with-apache-ossie](04-semantic-model-with-apache-ossie/) | [Watch on YouTube](https://youtu.be/6fAn39bPZb0) |
| 5 | Context layers for AI agents | [05-context-layers-for-ai](05-context-layers-for-ai/) | [Watch on YouTube](https://youtu.be/DSXlY7Gruhg) |
| 6 | One business, four models: taxonomy, ontology, knowledge graph and semantic layer | [06-one-business-four-models](06-one-business-four-models/) | [Watch on YouTube](https://youtu.be/3Nr_XUtVRY4) |
| 7 | One flight disruption, six data and AI trends: residency, decisions, governance, streaming, data quality and GraphRAG | [07-one-disruption-six-trends](07-one-disruption-six-trends/) | Coming soon |

## How to use this repo

1. Open the folder for the video you are on and read its README.
2. Recreate the same items in your own Microsoft Fabric workspace. A Fabric-enabled capacity is required.
3. Upload or regenerate the sample data, then run the KQL files in the default queryset.

Folders 03 to 07 run locally with Python (SQLite, DuckDB, rdflib and networkx); their READMEs list what to install.

Do not put passwords, connection strings, workspace or tenant identifiers, or other private details into this repo.

## Prerequisites

For the Fabric videos (1 and 2):

- A Microsoft Fabric workspace on a Fabric-enabled capacity
- Permission to create items in that workspace

## Official starting points

- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Get started with Real-Time Intelligence](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/get-started-with-real-time-intelligence)
