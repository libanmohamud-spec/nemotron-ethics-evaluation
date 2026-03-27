#!/usr/bin/env bash
set -euo pipefail
# Nemotron-Content-Safety-Reasoning-4B via vLLM OpenAI-compatible API (port 8001)
# Cap context: model card allows 128K but KV cache for that size needs huge VRAM.
python -m vllm.entrypoints.openai.api_server \
  --model nvidia/Nemotron-Content-Safety-Reasoning-4B \
  --port 8001 \
  --dtype bfloat16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90
