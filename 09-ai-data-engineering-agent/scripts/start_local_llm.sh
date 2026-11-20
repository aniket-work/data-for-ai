#!/usr/bin/env bash
# Start a small local model behind an OpenAI-compatible API on port 8998 with llama.cpp.
#   scripts/start_local_llm.sh path/to/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
# Get llama.cpp from https://github.com/ggml-org/llama.cpp/releases and the model from
# https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF . --jinja turns on tool calling.
# Already run Ollama, LM Studio, vLLM or oMLX? Skip this and set DATA_AGENT_BASE_URL / DATA_AGENT_MODEL instead.
set -euo pipefail
MODEL="${1:?usage: start_local_llm.sh model.gguf}"
exec llama-server -m "$MODEL" --jinja -c 16384 --host 127.0.0.1 --port "${PORT:-8998}" --alias qwen3-4b-instruct-2507
