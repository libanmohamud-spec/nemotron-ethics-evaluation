# Nemotron + vLLM on Windows (PowerShell). Requires NVIDIA GPU + CUDA PyTorch.
# Usage: .\start_server.ps1
# Or from Git Bash / WSL: bash start_server.sh

$ErrorActionPreference = "Stop"
if (-not $env:VLLM_USE_V1) { $env:VLLM_USE_V1 = "0" }
if (-not $env:PYTORCH_CUDA_ALLOC_CONF) { $env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True" }
$maxLen = if ($env:VLLM_MAX_MODEL_LEN) { $env:VLLM_MAX_MODEL_LEN } else { "4096" }

python -m vllm.entrypoints.openai.api_server `
  --model nvidia/Nemotron-Content-Safety-Reasoning-4B `
  --port 8001 `
  --dtype bfloat16 `
  --max-model-len $maxLen `
  --gpu-memory-utilization 0.85 `
  --enforce-eager
