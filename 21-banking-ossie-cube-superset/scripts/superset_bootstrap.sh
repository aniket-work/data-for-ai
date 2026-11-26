#!/usr/bin/env bash
# First-boot Superset init, then run the web server.
set -euo pipefail

MARKER=/app/superset_home/.banking_cube_bootstrapped
CUBE_URI="postgresql+psycopg2://cube:cube@cube:15432/db"

echo "== Superset bootstrap =="
superset db upgrade

if [ ! -f "$MARKER" ]; then
  echo "creating admin user (${ADMIN_USERNAME:-admin})"
  superset fab create-admin \
    --username "${ADMIN_USERNAME:-admin}" \
    --firstname Admin \
    --lastname User \
    --email "${ADMIN_EMAIL:-admin@example.com}" \
    --password "${ADMIN_PASSWORD:-admin}" || true
  superset init
  mkdir -p "$(dirname "$MARKER")"
  touch "$MARKER"
  echo "ok  first-boot admin/init complete"
else
  echo "ok  already bootstrapped"
fi

# Best-effort: register Cube SQL API (Postgres wire). Failures do not block the UI.
if command -v superset >/dev/null 2>&1; then
  if superset set-database-uri -d "Cube SQL API" -u "$CUBE_URI" 2>/dev/null; then
    echo "ok  registered database: Cube SQL API"
  else
    # Fallback for builds without set-database-uri.
    python <<'PY' || echo "warn: could not auto-register Cube SQL API (add it manually in Superset UI)"
from flask import Flask
from superset.app import create_app

app = create_app()
with app.app_context():
    from superset.extensions import db
    from superset.models.core import Database

    uri = "postgresql+psycopg2://cube:cube@cube:15432/db"
    existing = (
        db.session.query(Database).filter_by(database_name="Cube SQL API").one_or_none()
    )
    if existing is None:
        database = Database(database_name="Cube SQL API", sqlalchemy_uri=uri)
        database.set_sqlalchemy_uri(uri)
        db.session.add(database)
        db.session.commit()
        print("registered database: Cube SQL API")
    else:
        print("database already registered")
PY
  fi
fi

echo "starting Superset on :8088"
exec /usr/bin/run-server.sh
