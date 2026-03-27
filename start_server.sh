#!/usr/bin/env bash
set -euo pipefail
# Nemotron-Content-Safety-Reasoning-4B via vLLM OpenAI-compatible API (port 8001)
python -m vllm.entrypoints.openai.api_server \
  --model nvidia/Nemotron-Content-Safety-Reasoning-4B \
  --port 8001 \
  --dtype bfloat16
