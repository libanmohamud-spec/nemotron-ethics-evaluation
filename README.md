# nemotron-ethics-evaluation

Ethical evaluation framework for Nemotron-Content-Safety-Reasoning-4B.

## Run locally (GPU)

You need an **NVIDIA GPU** with enough VRAM (≈16 GB+ for this 4B model with vLLM; **more is easier**), **CUDA drivers** installed, and **Python 3.10+**.

### 1. Environment

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -U pip
# Install CUDA PyTorch first (pick the wheel index that matches your CUDA / PyTorch docs):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

If `nvidia-smi` works in a terminal but `python -c "import torch; print(torch.cuda.is_available())"` prints `False`, fix PyTorch/CUDA before continuing.

### 2. Hugging Face (if the model is gated)

```bash
set HF_TOKEN=your_token
set HUGGING_FACE_HUB_TOKEN=%HF_TOKEN%
```

(Linux/macOS: `export HF_TOKEN=...`.)

### 3. Start vLLM (terminal 1)

Leave this running. It serves OpenAI-compatible HTTP on **port 8001** (see `config/config.yml`).

- **Linux / macOS / Git Bash / WSL:** `bash start_server.sh`
- **Windows PowerShell:** `.\start_server.ps1`

Optional: `set VLLM_MAX_MODEL_LEN=2048` before starting if you hit VRAM limits.

### 4. Run evaluations (terminal 2)

From the **repository root** (same folder as `config/`):

```bash
python run_functional_tests.py
python run_ethical_tests.py
python generate_audit_log.py
python summarise_results.py
```

Outputs go under `evidence/functional/` and `evidence/ethical/`.

### Colab

Use `nemotron_ethics_evaluation.ipynb` on a **GPU** runtime (A100 recommended when available).
