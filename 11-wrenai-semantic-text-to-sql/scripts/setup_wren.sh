#!/usr/bin/env bash
# Point WrenAI at the Lesson 10 DuckDB warehouse, compile the MDL project and index the local memory.
# Run from anywhere, inside the virtual environment:  bash scripts/setup_wren.sh
set -euo pipefail
cd "$(dirname "$0")/.."
WH="$(cd ../10-metricflow-banking-metrics/warehouse 2>/dev/null && pwd || true)"
if [ -z "$WH" ] || [ ! -f "$WH/bank.duckdb" ]; then
  echo "Build the Lesson 10 warehouse first: see README, step 1." >&2; exit 1
fi
PROFILE="$(mktemp)"
printf '{"datasource": "duckdb", "format": "duckdb", "url": "%s"}\n' "$WH" > "$PROFILE"
wren profile add kestrel_bay_bank --from-file "$PROFILE" --activate
rm -f "$PROFILE"
cd wren_bank
wren context validate
wren context build
wren memory index --no-seed
