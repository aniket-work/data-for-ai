# 21 — Bank KPIs from Apache OSSIE: Cube, ClickHouse and Superset

**Stack:** Apache OSSIE (incubating) package → official `apache-ossie-cube` converter → Cube Core → ClickHouse → Apache Superset
**Bank:** Happn Community Bank (fictional; all names and figures are made up)

## Learning objective

Metrics, dimensions, joins, **and business conditions** come from one Apache OSSIE
package. Cube and Superset only consume it: no hand-written KPI SQL in the Cube model.

## What is OSSIE vs what is presentation

| Concern | Lives in the Apache OSSIE package | Presentation only |
|---------|-----------------------------------|-------------------|
| Dataset / field / join schema | `ossie/semantic_model.yaml` | Cube dimensions/joins generated from it |
| KPI formulas (`total_deposits`, `npl_ratio`, …) | `semantic_model.yaml` → `metrics` | Cube measures from the **official** `apache-ossie-cube` converter; always a subset of the OSSIE metrics |
| Business conditions | `ontology.yaml` `requires` / `derived_by` / `annotations` / `ai_context` | Markdown catalog + compiled violation measures (the Cube converter does **not** load the ontology) |
| Physical tables | — | ClickHouse DDL + CSV load (**not** Cube / OSSIE) |
| Dashboard layout / viz types | — | Superset charts |

## Run the demo

Prerequisites: Docker with Docker Compose, Python 3, network access to pull images.

```bash
cd 21-banking-ossie-cube-superset
./run-local.sh
```

That script:

1. Checks that the OSSIE package in `ossie/` is present
2. Runs the **official** converter via `scripts/ossie_to_cube.py` (apache-ossie-cube), binds each cube's `sql_table` to the demo ClickHouse tables, and compiles the ontology catalog and violation measures (`scripts/ossie_ontology_to_showcase.py`)
3. Starts ClickHouse + Cube (+ Superset) with Docker Compose
4. Loads `data/*.csv` into ClickHouse
5. Asserts the KPIs through the Cube REST API (`checks/expected_ossie_kpis.json`) and checks the deposit concentration condition
6. Prints the service links
7. Seeds Superset: OSSIE KPI tiles + ontology Markdown + violation big-numbers

| Service | URL / endpoint |
|---------|----------------|
| Cube Playground | http://127.0.0.1:4000 |
| Cube SQL API (Postgres wire) | `127.0.0.1:35432`, user `cube`, password `cube`, db `db` (local demo defaults) |
| ClickHouse HTTP | http://127.0.0.1:8124 |
| Superset | http://127.0.0.1:8088, login `admin` / `admin` (local demo defaults; change them for anything shared) |
| OSSIE showcase dashboard | http://127.0.0.1:8088/superset/dashboard/happn-banking-kpis/ |

```bash
./run-local.sh --no-superset   # faster: ClickHouse + Cube only
./run-local.sh --smoke-only    # re-check KPIs against a running Cube
./run-local.sh --down          # stop containers

# Re-seed / refresh the Superset dashboard only:
.runtime/venv/bin/python scripts/seed_superset_dashboard.py
```

After login, open **Dashboards → Happn Banking — Apache OSSIE definitions**.

## Change a definition, regenerate

The OSSIE package is the source of truth. To change a KPI, edit it in
`ossie/semantic_model.yaml` (for example, count loans 30+ days past due as non-performing
in `npl_principal` / `npl_ratio`), then regenerate:

```bash
.runtime/venv/bin/python scripts/ossie_to_cube.py
.runtime/venv/bin/python scripts/ossie_ontology_to_showcase.py
```

Cube (dev mode) reloads the model and the Superset tiles follow. Note that
`checks/expected_ossie_kpis.json` holds the values for the original definitions, so the
smoke test is expected to flag the difference until you restore or update it.

## Entities

Customer · Account · Transaction · Loan · Branch · Risk rating
(4 branches, 10 customers, 18 accounts, 20 transactions, 8 loans, 10 risk ratings)

## Demonstrate

- Total deposits → `bank_account.total_deposits` (expected **2,062,500**)
- Non-performing loans → `loan.npl_principal` **57,000** of `loan.total_principal` **2,392,000**
- NPL ratio → `loan.npl_ratio` (expected **≈ 0.0238**)
- Transaction volume → `transaction.transaction_volume` (expected **375,427.54**)
- Customer concentration risk → `bank_account.customer_deposit_share` by `customer_id` (CU-1008 holds 1,045,000 = 50.7%, above the 25% limit)
- Branch view → deposits vs loan principal by branch

## Business conditions (from `ossie/ontology.yaml`)

| Condition | Requires | Authority |
|-----------|----------|-----------|
| OpenAccountDepositRule | `account_status = 'open'` | Happn Treasury Policy |
| NPLClassificationRule | `days_past_due >= 90 OR is_non_performing_loan` | Happn Credit Risk Policy |
| SingleCustomerDepositConcentrationWarning | customer share of open deposits ≤ 25% | Happn Liquidity Risk Policy |
| LargeExposureApprovalRule | `principal_amount >= 300000000` (KRW, demo threshold) | RiskCommittee |

## Layout

```
21-banking-ossie-cube-superset/
  ossie/                 # Apache OSSIE package: semantic_model, ontology, mapping, validation
  data/                  # demo CSVs loaded into ClickHouse
  cube/                  # Cube Core config + generated model/
  clickhouse/init/       # DDL
  superset/              # Superset config (+ generated ontology catalog)
  scripts/               # converter wrapper, ontology showcase, load, smoke, Superset seeding
  checks/                # expected KPI values (generated)
  docker-compose.yml
  run-local.sh           # one-command demo
  requirements.txt       # local venv under .runtime/ (created by run-local)
```

## Links

- Apache OSSIE: https://ossie.apache.org/
- Cube Core: https://cube.dev/docs · https://github.com/cube-js/cube
- Apache Superset: https://superset.apache.org/
- ClickHouse: https://clickhouse.com/docs

Stop with `./run-local.sh --down`. Runtime state is Docker volumes + `.runtime/` (gitignored).

---

Apache OSSIE is an effort undergoing incubation at The Apache Software Foundation (ASF),
sponsored by the Apache Incubator. Incubation is required of all newly accepted projects
until a further review indicates that the infrastructure, communications, and decision
making process have stabilized in a manner consistent with other successful ASF projects.
While incubation status is not necessarily a reflection of the completeness or stability
of the code, it does indicate that the project has yet to be fully endorsed by the ASF.
Apache, Apache Superset and the Apache feather logo are trademarks of The Apache Software
Foundation. Cube and ClickHouse are trademarks of their respective owners. This is an
independent educational demo, not affiliated with or endorsed by these projects.
