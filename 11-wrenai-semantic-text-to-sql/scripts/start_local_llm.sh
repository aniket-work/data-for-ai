#!/usr/bin/env bash
# Start a local OpenAI-compatible model server with llama.cpp (https://github.com/ggml-org/llama.cpp).
# The video used Qwen3-4B-Instruct-2507 (Q4_K_M GGUF) on CPU. Any OpenAI-compatible server works:
# set T2S_BASE_URL (and T2S_MODEL / T2S_API_KEY if needed) to point the harness at it.
#
#   LLAMA_SERVER=/path/to/llama-server MODEL=/path/to/Qwen3-4B-Instruct-2507-Q4_K_M.gguf bash scripts/start_local_llm.sh
#
# Get the model, for example:  hf download Qwen/Qwen3-4B-Instruct-2507-GGUF Qwen3-4B-Instruct-2507-Q4_K_M.gguf --local-dir models
set -euo pipefail
LLAMA_SERVER="${LLAMA_SERVER:-llama-server}"
MODEL="${MODEL:-models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf}"
PORT="${PORT:-8999}"
# --cache-ram keeps llama.cpp's prompt cache small (its 8 GB default can exhaust RAM on a laptop).
exec "$LLAMA_SERVER" -m "$MODEL" --jinja -c 16384 --parallel 1 -fa on --cache-ram 512 \
  --host 127.0.0.1 --port "$PORT" --alias qwen3-4b-instruct-2507
