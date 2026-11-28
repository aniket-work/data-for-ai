#!/usr/bin/env bash
# Load generated Turtle into Fuseki dataset ``happn`` (replace graph).
set -euo pipefail

ROOT_UC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TTL="${1:-$ROOT_UC/rdf/banking.ttl}"
BASE="${FUSEKI_BASE:-http://127.0.0.1:3030}"
USER="${FUSEKI_USER:-admin}"
PASS="${FUSEKI_PASSWORD:-admin}"
DS="${FUSEKI_DATASET:-happn}"

if [ ! -f "$TTL" ]; then
  echo "error: missing $TTL — run scripts/ossie_to_rdf.py first" >&2
  exit 1
fi

echo "loading rdf/$(basename "$TTL") → $BASE/$DS/data"
# Clear then PUT the graph (GSP)
curl -fsS -u "$USER:$PASS" -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @"$TTL" \
  "$BASE/$DS/data" >/dev/null

echo "ok  loaded into dataset $DS"
# Quick count
curl -fsS -u "$USER:$PASS" \
  --data-urlencode "query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }" \
  "$BASE/$DS/sparql" | head -c 400
echo
