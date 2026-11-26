# Warehouse binding (not semantic conversion)

`scripts/ossie_to_cube.py` uses the **official** `apache-ossie-cube` converter
(`ossie-cube export`) for all datasets / fields / joins / metrics.

The only custom step afterward is rewriting Cube `sql_table` from the source
string declared on each OSSIE dataset:

```text
core_banking.public.accounts
  → banking.accounts   (ClickHouse demo DB created by clickhouse/init + load_clickhouse.sh)
```

That is deployment binding to an already-loaded warehouse. It is **not** an
OSSIE→Cube translator and must not grow measure/join logic.
