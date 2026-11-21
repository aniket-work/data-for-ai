#!/usr/bin/env bash
# Installs Cube Core (npm, no Docker) and writes cube/.env with fresh random secrets.
set -euo pipefail
cd "$(dirname "$0")/../cube"
npm install --no-audit --no-fund
npm rebuild @cubejs-backend/native   # native module for the SQL API (npm 11+ may skip install scripts)
if [ ! -f .env ]; then
  cp .env.example .env
  echo "CUBEJS_API_SECRET=$(openssl rand -hex 32)" >> .env
  echo "CUBEJS_SQL_PASSWORD=$(openssl rand -hex 12)" >> .env
  echo "wrote cube/.env (keep it private)"
fi
