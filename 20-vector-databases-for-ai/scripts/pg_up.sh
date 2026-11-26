#!/usr/bin/env bash
# A throwaway local PostgreSQL 17 + pgvector for the comparison (no Docker). Data lives in .pg/ (git-ignored).
# Debian/Ubuntu: sudo apt-get install postgresql-17 postgresql-17-pgvector
set -euo pipefail
cd "$(dirname "$0")/.."
BIN=${PG_BIN:-/usr/lib/postgresql/17/bin}; PORT=${PG_PORT:-55432}; SOCK=${PG_SOCK:-/tmp/kbank_pg}
mkdir -p "$SOCK"
[ -d .pg ] || "$BIN/initdb" -D .pg -U kbank --auth=trust -E UTF8 >/dev/null
"$BIN/pg_ctl" -D .pg -o "-p $PORT -k $SOCK -c listen_addresses='' -c maintenance_work_mem=512MB -c shared_buffers=256MB" -l .pg/server.log -w start >/dev/null
echo "postgres $("$BIN/postgres" --version | awk '{print $3}') running on socket $SOCK port $PORT"
