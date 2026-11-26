#!/usr/bin/env bash
# Happn Community Bank demo: Apache OSSIE → Cube → ClickHouse → Superset.
#
# Usage (from this folder):
#   ./run-local.sh                # convert OSSIE, start stack, load data, KPI smoke, seed Superset
#   ./run-local.sh --no-open      # same without opening browsers
#   ./run-local.sh --no-superset  # ClickHouse + Cube only (faster)
#   ./run-local.sh --smoke-only   # re-run KPI checks against a running Cube
#   ./run-local.sh --down         # stop and remove containers
set -euo pipefail

ROOT_UC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_UC"

OPEN_BROWSER=1
WITH_SUPERSET=1
SMOKE_ONLY=0
DO_DOWN=0

usage() {
  cat <<'USAGE'
Happn Community Bank demo (Apache OSSIE → Cube → ClickHouse → Superset).

  ./run-local.sh [--no-open] [--no-superset] [--smoke-only] [--down]

URLs after a successful start:
  Cube Playground  http://127.0.0.1:4000
  Cube SQL API     postgres://127.0.0.1:35432/db
  ClickHouse HTTP  http://127.0.0.1:8124
  Superset         http://127.0.0.1:8088  (demo login: see README)
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --no-open) OPEN_BROWSER=0; shift ;;
    --no-superset) WITH_SUPERSET=0; shift ;;
    --smoke-only) SMOKE_ONLY=1; shift ;;
    --down) DO_DOWN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

COMPOSE=(docker compose -f "$ROOT_UC/docker-compose.yml")
VENV="$ROOT_UC/.runtime/venv"
PY="$VENV/bin/python"

ensure_python() {
  [ -x "$PY" ] && return 0
  have python3 || die "python3 is required"
  say "[deps] creating $VENV"
  mkdir -p "$ROOT_UC/.runtime"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$ROOT_UC/requirements.txt"
}

open_url() {
  [ "$OPEN_BROWSER" = 1 ] || return 0
  if have open; then open "$1" >/dev/null 2>&1 || true
  elif have xdg-open; then xdg-open "$1" >/dev/null 2>&1 || true
  fi
}

if [ "$DO_DOWN" = 1 ]; then
  say "== stopping banking stack =="
  "${COMPOSE[@]}" down --remove-orphans
  say "ok  stopped"
  exit 0
fi

if [ "$SMOKE_ONLY" = 1 ]; then
  ensure_python
  "$PY" "$ROOT_UC/scripts/smoke_kpis.py"
  exit 0
fi

have docker || die "docker is required"
docker compose version >/dev/null 2>&1 || die "docker compose is required"

say "== Happn Community Bank: Apache OSSIE → Cube → ClickHouse → Superset =="

# 1) The OSSIE package is the contract (semantic_model, ontology, mapping, validation)
[ -f "$ROOT_UC/ossie/semantic_model.yaml" ] || die "missing ossie/semantic_model.yaml"
say "[1/7] OSSIE package present (ossie/)"
ensure_python

# 2) Cube model from OSSIE metrics (official converter) + ontology showcase
say "[2/7] generating Cube model (official ossie-cube) + ontology catalog"
"$PY" "$ROOT_UC/scripts/ossie_to_cube.py"
"$PY" "$ROOT_UC/scripts/ossie_ontology_to_showcase.py"

# 3) Containers
if [ "$WITH_SUPERSET" = 1 ]; then
  say "[3/7] starting ClickHouse + Cube + Superset"
  "${COMPOSE[@]}" up -d clickhouse cube superset_db superset
else
  say "[3/7] starting ClickHouse + Cube (--no-superset)"
  "${COMPOSE[@]}" up -d clickhouse cube
fi
say "  waiting for ClickHouse …"
for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:8124/ping" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:8124/ping" >/dev/null || die "ClickHouse did not become ready on :8124"

# 4) Physical tables + data (ClickHouse DDL + CSV; Cube never creates tables)
say "[4/7] loading CSV data into ClickHouse"
bash "$ROOT_UC/scripts/load_clickhouse.sh"

# 5) KPI smoke against Cube REST
say "[5/7] smoke-testing Cube KPIs from OSSIE metrics"
"$PY" "$ROOT_UC/scripts/smoke_kpis.py" --base "http://127.0.0.1:4000"

# 6–7) URLs + Superset dashboard
say "[6/7] ready"
say "  Cube Playground  http://127.0.0.1:4000"
say "  ClickHouse HTTP  http://127.0.0.1:8124"
if [ "$WITH_SUPERSET" = 1 ]; then
  say "  Superset         http://127.0.0.1:8088"
  say "  Cube SQL API     127.0.0.1:35432 (Postgres wire)"
  for _ in $(seq 1 90); do
    curl -fsS "http://127.0.0.1:8088/health" >/dev/null 2>&1 && break
    sleep 2
  done
  if curl -fsS "http://127.0.0.1:8088/health" >/dev/null 2>&1; then
    say "[7/7] seeding Superset dashboard (OSSIE KPIs + ontology conditions + violations)"
    "$PY" "$ROOT_UC/scripts/seed_superset_dashboard.py" --base "http://127.0.0.1:8088" || \
      say "  warn: dashboard seed failed; run: .runtime/venv/bin/python scripts/seed_superset_dashboard.py"
    open_url "http://127.0.0.1:8088/superset/dashboard/happn-banking-kpis/"
  else
    say "  warn: Superset not healthy yet; open http://127.0.0.1:8088 later"
  fi
fi
open_url "http://127.0.0.1:4000"
say "ok  demo stack is up (stop with: ./run-local.sh --down)"
