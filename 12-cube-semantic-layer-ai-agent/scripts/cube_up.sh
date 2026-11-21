#!/usr/bin/env bash
# Start Cube Core in the background, wait until it is ready, show its startup lines.
# Logs go to cube.log; stop it with: pkill -f cubejs-server
set -euo pipefail
cd "$(dirname "$0")/.."
(cd cube && nohup npx cubejs-server > ../cube.log 2>&1 &)
for _ in $(seq 60); do
  curl -sf http://localhost:4000/readyz > /dev/null && break
  sleep 0.5
done
cat cube.log
curl -s http://localhost:4000/readyz; echo
