#!/usr/bin/env bash
set -euo pipefail

# The upstream project pins Python 3.10 and PyTorch 2.9. CUDA 12.8 is the
# appropriate PyTorch wheel channel for RTX PRO 6000 Blackwell systems.
CONDA_BASE="${CONDA_BASE:-/vol/dissolve/justin/miniforge3}"
UPSTREAM_CONDA_ENV="${UPSTREAM_CONDA_ENV:-lingbot_va_upstream}"
PYTORCH_INDEX_URL="${PYTORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"

if ! conda env list | awk '{print $1}' | grep -Fxq "${UPSTREAM_CONDA_ENV}"; then
  conda create -y -n "${UPSTREAM_CONDA_ENV}" python=3.10.16
fi
conda activate "${UPSTREAM_CONDA_ENV}"

python -m pip install --upgrade pip
python -m pip install \
  torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 \
  --index-url "${PYTORCH_INDEX_URL}"
python -m pip install \
  diffusers==0.36.0 \
  transformers==4.55.2 \
  accelerate \
  einops \
  easydict \
  'numpy==1.26.4' \
  tqdm \
  'imageio[ffmpeg]' \
  websockets \
  msgpack \
  opencv-python \
  matplotlib \
  ftfy \
  safetensors \
  'huggingface-hub[cli]==0.36.2' \
  Pillow \
  wandb

python - <<'PY'
import torch

assert torch.__version__.startswith("2.9."), torch.__version__
assert torch.cuda.is_available(), "CUDA is not visible in the upstream environment"
print("PyTorch:", torch.__version__)
print("CUDA runtime:", torch.version.cuda)
print("GPUs:", torch.cuda.device_count())
for index in range(torch.cuda.device_count()):
    print(index, torch.cuda.get_device_name(index), torch.cuda.get_device_properties(index).total_memory)
PY

echo "Upstream environment ready: ${UPSTREAM_CONDA_ENV}"
