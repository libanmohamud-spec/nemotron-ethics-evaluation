#!/usr/bin/env bash
set -euo pipefail
# Nemotron-Content-Safety-Reasoning-4B via vLLM OpenAI-compatible API (port 8001)
# Cap context; optional: export VLLM_MAX_MODEL_LEN=2048 for tighter VRAM.
export VLLM_USE_V1="${VLLM_USE_V1:-0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
python -m vllm.entrypoints.openai.api_server \
  --model nvidia/Nemotron-Content-Safety-Reasoning-4B \
  --port 8001 \
  --dtype bfloat16 \
  --max-model-len "${VLLM_MAX_MODEL_LEN:-4096}" \
  --gpu-memory-utilization 0.85 \
  --enforce-eager
