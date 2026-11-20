#!/usr/bin/env bash
# Start the Saiku 4.8.0 release JAR in demo mode on localhost, with our SQL-trace logging config.
# Usage: scripts/start_saiku.sh <path-to-saiku-jar> <absolute-saiku-home>
set -euo pipefail
JAR="$1"; HOME_DIR="$2"; HERE="$(cd "$(dirname "$0")/.." && pwd)"
pkill -f "saiku-.*\.jar serve" 2>/dev/null && sleep 3 || true
mkdir -p "$HOME_DIR/logs"
SAIKU_DEMO=true nohup java -Xmx1200m -XX:+ExitOnOutOfMemoryError -XX:-UseBASE64Intrinsics \
  -Dsaiku.security.acknowledged=true \
  -Dlog4j2.configurationFile="$HERE/saiku/log4j2-sql.xml" \
  -jar "$JAR" serve --home "$HOME_DIR" --host 127.0.0.1 --port 8080 > saiku-console.log 2>&1 &
for i in $(seq 1 90); do
  if grep -q "Saiku ready" saiku-console.log 2>/dev/null; then grep -A3 "Saiku ready" saiku-console.log; exit 0; fi
  sleep 1
done
echo "Saiku did not start; see saiku-console.log" >&2; exit 1
