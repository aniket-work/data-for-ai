# Lesson 18: Virtual Knowledge Graphs (Ontop + SPARQL over live PostgreSQL)

Query live relational tables as a knowledge graph **without copying them**. An OWL 2 QL ontology gives the tables business
meaning, mappings say how each term is computed in SQL, and [Ontop](https://ontop-vkg.org) rewrites every SPARQL query
into one SQL query at request time. Then we measure it against the classic ETL copy into a triple store.

Video: Data for AI, Lesson 18 (link in the root README).

## The scenario (fictional)

**Alder & Finch Outdoor** runs three legacy systems in one PostgreSQL database, with cryptic names:

| table | holds | rows |
|---|---|---|
| `crm.cst_mstr` | customers (IDs only, no personal data) | 12,000 |
| `erp.sup_mstr` | suppliers | 6 |
| `erp.prd_mstr` | products, `cat_cd` TNT / PCK / STV / SLB | 34 |
| `erp.ord_hdr` | orders | 60,000 |
| `erp.ord_ln` | order lines | 129,621 |
| `svc.wrty_tkt` | warranty tickets, `sts_cd` O / C / W | 4,596 |

The question: *which suppliers have tents with warranty claims open more than 14 days, and how many customers are waiting?*

## Files

```
db/build_data.py           seeded generator (seed 18, "today" = 2026-11-20) -> PostgreSQL
vkg/alderfinch.ttl         ontology (OWL 2 QL): Product > Tent/Backpack/Stove/SleepingBag, WarrantyClaim > OpenClaim, ...
vkg/alderfinch.obda        13 Ontop mappings (target graph template + source SQL)
vkg/alderfinch.r2rml.ttl   the same mappings in W3C R2RML (generated with `ontop mapping to-r2rml`)
vkg/alderfinch.properties  JDBC settings for the local database
vkg/fabric.properties.example   placeholders for a Microsoft Fabric Warehouse / SQL analytics endpoint (not executed)
sparql/q1..q5              the questions, in SPARQL
vkg.py                     the demo CLI (below)
runs/                      the measured numbers from the recorded run
diagrams/                  the two diagrams from the video (interactive HTML, JSON source, PNG)
docs/slides.pdf            the slides from the video
```

## Run it

You need Python 3.11+, PostgreSQL, Java 17+ and the Ontop CLI (tested with 5.5.0 and Java 21).

```bash
# 1. PostgreSQL. Local demo only: trust auth on localhost, no password. Never do this on a shared machine.
docker run -d --name alderfinch-pg -p 5432:5432 -e POSTGRES_USER=vkg -e POSTGRES_DB=alderfinch \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17

# 2. Ontop CLI + PostgreSQL JDBC driver
curl -LO https://github.com/ontop/ontop/releases/download/ontop-5.5.0/ontop-cli-5.5.0.zip && unzip ontop-cli-5.5.0.zip -d ontop
curl -L -o ontop/jdbc/postgresql-42.7.4.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar
export ONTOP_CLI=$PWD/ontop/ontop

# 3. Python side
pip install -r requirements.txt
python db/build_data.py

# 4. The lesson
python vkg.py up                 # start the Ontop SPARQL endpoint (dev mode, reloads the mapping) and time the first answer
python vkg.py tables             # the legacy tables
python vkg.py mapping            # ontology + mapping excerpts
python vkg.py ask q2 --sql       # SPARQL answer from the live tables, plus the SQL Ontop generated
python vkg.py ask q3 --sql       # subclass reasoning compiled into SQL
python vkg.py etl                # the "before": materialize all triples and load them into Oxigraph
python vkg.py compare            # same 4 queries on both engines: answers and median times
python vkg.py live               # close 25 claims, open 1: who sees it?
python vkg.py schema-change      # rename a column; fix 2 mapping lines; compare recovery
python vkg.py scorecard          # everything measured, in one table
python vkg.py fabric             # the Microsoft Fabric configuration (placeholders, not executed)
python vkg.py reset              # rebuild data, restore the mapping, drop the copy
```

Environment variables: `VKG_DSN` (default `postgresql://vkg@127.0.0.1:5432/alderfinch`), `VKG_ENDPOINT`
(default `http://127.0.0.1:8090`), `ONTOP_CLI` (default `ontop` on PATH).

You can also query the endpoint directly at `http://127.0.0.1:8090/sparql`, or use the Ontop CLI without an endpoint:

```bash
$ONTOP_CLI query -t vkg/alderfinch.ttl -m vkg/alderfinch.obda -p vkg/alderfinch.properties -q sparql/q2_open_tent_claims.rq
```

## Measured on the recording box (yours will differ)

| | ETL copy (before) | Virtual KG (after) |
|---|---|---|
| Extra storage | 235.2 MB (956,476 triples: 141.4 MB N-Triples + 93.8 MB Oxigraph store) | 0 MB (about 5 KB of ontology + mapping) |
| Before the first answer | 12.9 s (materialize 11.5 s + load 1.4 s) | 3.2 s endpoint start |
| 25 claims closed, 1 opened | stale: 354 open, 0 new | live: 329 open, 1 new |
| Column renamed | silent stale data; 13.4 s rebuild after the same mapping fix | loud error; 2-line mapping fix, answering again in 0.9 s |
| Median query time q1/q2/q3/q4 | 0.4 / 36.0 / 0.1 / 14.6 ms | 5.9 / 7.6 / 5.0 / 7.2 ms |
| Same answers on fresh data | yes | yes |

Source tables: 21.6 MB. The copy is 10.9x that (the store alone 4.3x). Both engines run on one small Linux box with warm caches.

## Microsoft Fabric

A Fabric Warehouse and a Lakehouse SQL analytics endpoint both accept T-SQL over TDS (port 1433) with Microsoft Entra ID
authentication only (no SQL authentication). Ontop supports SQL Server, so the same ontology and mapping can target them
with the `mssql-jdbc` driver (plus `msal4j` for Entra sign-in) and your schema names. See `vkg/fabric.properties.example`.
This part was **not executed** in the lesson (no Fabric capacity used): check the generated SQL against the Warehouse
T-SQL surface area before relying on it.

## Notes

- `vkg.py` is a teaching CLI. The VKG engine is Ontop; the triple-store copy uses `ontop materialize` + pyoxigraph.
- `schema-change` edits `vkg/alderfinch.obda` in place (backup in `runs/`); `reset` restores it.
- All company, supplier and product names are fictional. No personal data.
