#!/usr/bin/env bash
# Start the banking knowledge-graph demo: Apache OSSIE → RDF → Apache Jena Fuseki → SPARQL checks.
#
# Usage (from this folder):
#   ./run-local.sh
#   ./run-local.sh --no-open
#   ./run-local.sh --smoke-only
#   ./run-local.sh --down
set -euo pipefail

ROOT_UC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_UC"

export PATH="/usr/local/bin:/opt/homebrew/bin:${HOME}/.local/bin:${PATH}"

OPEN_BROWSER=1
SMOKE_ONLY=0
DO_DOWN=0

usage() {
  cat <<'USAGE'
Banking knowledge-graph demo (Apache OSSIE → RDF → Apache Jena Fuseki).

  ./run-local.sh
  ./run-local.sh --no-open
  ./run-local.sh --smoke-only
  ./run-local.sh --down
  ./run-local.sh -h | --help

URLs after a successful start:
  Fuseki UI        http://127.0.0.1:3030/   (login: see README)
  SPARQL endpoint  http://127.0.0.1:3030/happn/sparql
  Explorer         explorer/index.html
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --no-open) OPEN_BROWSER=0; shift ;;
    --smoke-only) SMOKE_ONLY=1; shift ;;
    --down) DO_DOWN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

COMPOSE=(docker compose -f "$ROOT_UC/docker-compose.yml")
VENV="$ROOT_UC/.runtime/venv"
PY="$VENV/bin/python"

ensure_python() {
  if [ -x "$PY" ]; then
    return 0
  fi
  have python3 || die "python3 is required"
  say "[deps] creating .runtime/venv"
  mkdir -p "$ROOT_UC/.runtime"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$ROOT_UC/requirements.txt"
}

open_url() {
  local url="$1"
  if [ "$OPEN_BROWSER" != 1 ]; then
    return 0
  fi
  if have open; then
    open "$url" >/dev/null 2>&1 || true
  elif have xdg-open; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

if [ "$DO_DOWN" = 1 ]; then
  say "== stopping banking-jena stack =="
  "${COMPOSE[@]}" down --remove-orphans
  say "ok  stopped"
  exit 0
fi

if [ "$SMOKE_ONLY" = 1 ]; then
  ensure_python
  "$PY" "$ROOT_UC/scripts/smoke_sparql.py"
  exit $?
fi

have docker || die "docker is required"
docker compose version >/dev/null 2>&1 || die "docker compose is required"

say "== Banking knowledge graph from Apache OSSIE =="

# 1) OSSIE package
[ -f "$ROOT_UC/ossie/ontology.yaml" ] || die "missing ossie/ontology.yaml (the Apache OSSIE package)"
say "[1/5] Apache OSSIE package present (ossie/ontology.yaml, semantic_model.yaml, mapping.yaml)"
ensure_python

# 2) Convert OSSIE → Turtle
say "[2/5] converting OSSIE ontology + CSV → RDF (Turtle)"
"$PY" "$ROOT_UC/scripts/ossie_to_rdf.py" || die "ossie_to_rdf.py failed"

# 3) Start Fuseki
say "[3/5] starting Apache Jena Fuseki"
"${COMPOSE[@]}" up -d fuseki

say "  waiting for Fuseki …"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:3030/\$/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:3030/\$/ping" >/dev/null || die "Fuseki did not become ready on :3030"
# The image creates dataset "happn" a moment after the server answers ping.
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:3030/happn/sparql?query=ASK%7B%7D" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:3030/happn/sparql?query=ASK%7B%7D" >/dev/null || die "dataset happn did not appear"

# 4) Load Turtle
say "[4/5] loading Turtle into Fuseki dataset happn"
bash "$ROOT_UC/scripts/load_fuseki.sh" || die "load_fuseki.sh failed"

# 5) Smoke SPARQL
say "[5/5] smoke-testing SPARQL fixtures"
"$PY" "$ROOT_UC/scripts/smoke_sparql.py" --base "http://127.0.0.1:3030" || die "SPARQL smoke failed"

say "ready"
say "  Fuseki UI        http://127.0.0.1:3030/"
say "  SPARQL endpoint  http://127.0.0.1:3030/happn/sparql"
say "  Explorer         explorer/index.html"
open_url "http://127.0.0.1:3030/"
open_url "file://$ROOT_UC/explorer/index.html"
say "ok  demo stack is up (stop with: ./run-local.sh --down)"
