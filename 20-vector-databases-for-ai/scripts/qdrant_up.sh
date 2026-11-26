#!/usr/bin/env bash
# Run Qdrant as a plain binary (no Docker). Downloads the release once into .qdrant/bin, stores data in .qdrant/storage.
# Linux x86_64 uses the musl build (static, runs on older glibc). macOS: use the apple-darwin tarball instead.
set -euo pipefail
cd "$(dirname "$0")/.."
VER=${QDRANT_VERSION:-v1.20.2}; mkdir -p .qdrant/bin .qdrant/storage .qdrant/snapshots
if [ ! -x .qdrant/bin/qdrant ]; then
  curl -sL -o .qdrant/qdrant.tgz "https://github.com/qdrant/qdrant/releases/download/$VER/qdrant-x86_64-unknown-linux-musl.tar.gz"
  tar -xzf .qdrant/qdrant.tgz -C .qdrant/bin && rm .qdrant/qdrant.tgz
fi
if ! curl -sf localhost:6333/healthz >/dev/null 2>&1; then
  QDRANT__TELEMETRY_DISABLED=true QDRANT__STORAGE__STORAGE_PATH=.qdrant/storage QDRANT__STORAGE__SNAPSHOTS_PATH=.qdrant/snapshots \
    nohup .qdrant/bin/qdrant > .qdrant/qdrant.log 2>&1 &
  for i in $(seq 1 40); do curl -sf localhost:6333/healthz >/dev/null 2>&1 && break; sleep 0.25; done
fi
curl -s localhost:6333 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['title'], d['version'], '-> http://localhost:6333  (gRPC 6334)')"
