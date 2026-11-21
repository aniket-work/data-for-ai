#!/usr/bin/env bash
# Starts Cube Core on :4000 (REST + GraphQL) and :15432 (SQL API, Postgres wire protocol).
set -euo pipefail
cd "$(dirname "$0")/../cube"
exec npx cubejs-server
