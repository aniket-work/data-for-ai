#!/usr/bin/env bash
# Load Happn banking CSVs into the local ClickHouse container.
set -euo pipefail

ROOT_UC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT_UC/docker-compose.yml")
DATA="$ROOT_UC/data"
CH_CONTAINER="$("${COMPOSE[@]}" ps -q clickhouse)"

if [ -z "$CH_CONTAINER" ]; then
  echo "error: clickhouse container is not running (start with ./run-local.sh)" >&2
  exit 1
fi

say() { printf '%s\n' "$*"; }
CH_AUTH=(clickhouse-client --user banking --password banking)

say "== load ClickHouse banking tables =="
docker exec -i "$CH_CONTAINER" "${CH_AUTH[@]}" --multiquery <"$ROOT_UC/clickhouse/init/01_schema.sql"

# Truncate then insert (idempotent re-runs).
for table in branches customers accounts transactions loans risk_ratings; do
  docker exec "$CH_CONTAINER" "${CH_AUTH[@]}" -q "TRUNCATE TABLE IF EXISTS banking.${table}"
done

load_csv() {
  local table="$1" file="$2"
  say "  loading banking.${table} ← ${file##*/}"
  # CSVWithNames: header row matches CREATE TABLE column order.
  docker exec -i "$CH_CONTAINER" "${CH_AUTH[@]}" \
    --query="INSERT INTO banking.${table} FORMAT CSVWithNames" \
    <"$file"
}

load_csv branches "$DATA/branches.csv"
load_csv customers "$DATA/customers.csv"
load_csv accounts "$DATA/accounts.csv"
load_csv transactions "$DATA/transactions.csv"
load_csv loans "$DATA/loans.csv"
load_csv risk_ratings "$DATA/risk_ratings.csv"

say "  row counts:"
docker exec "$CH_CONTAINER" "${CH_AUTH[@]}" -q "
SELECT 'branches' AS t, count() FROM banking.branches
UNION ALL SELECT 'customers', count() FROM banking.customers
UNION ALL SELECT 'accounts', count() FROM banking.accounts
UNION ALL SELECT 'transactions', count() FROM banking.transactions
UNION ALL SELECT 'loans', count() FROM banking.loans
UNION ALL SELECT 'risk_ratings', count() FROM banking.risk_ratings
FORMAT PrettyCompact
"
say "ok  ClickHouse loaded"
