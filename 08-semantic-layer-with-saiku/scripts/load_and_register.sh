#!/usr/bin/env bash
# Load the Northlight Cinemas star schema into H2 and register the semantic layer with Saiku.
# Usage: scripts/load_and_register.sh <path-to-saiku-jar> <absolute-saiku-home>
# Stop Saiku first (H2 file databases allow one process at a time), then start it again.
set -euo pipefail
JAR="$1"; HOME_DIR="$2"; HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME_DIR/data" "$HOME_DIR/repository/data/unknown/datasources"
rm -f "$HOME_DIR"/data/northlight.*.db
java -cp "$JAR" org.h2.tools.RunScript -url "jdbc:h2:$HOME_DIR/data/northlight" -user sa \
     -script "$HERE/sql/northlight_h2.sql"
cp "$HERE/schema/NorthlightCinemas.xml" "$HOME_DIR/data/"
sed "s#@SAIKU_HOME@#$HOME_DIR#g" "$HERE/saiku/northlight.sds.template" \
    > "$HOME_DIR/repository/data/unknown/datasources/northlight.sds"
echo "Loaded data/northlight.mv.db and registered datasource 'northlight' (cube: Box Office)"
