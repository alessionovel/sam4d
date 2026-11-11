# Setup

The notebooks need **two separate conda environments**. Their dependencies conflict:

| | `.venv-sam3` (sam3.ipynb) | `.venv-sam3d` (sam3d.ipynb) |
|---|---|---|
| Python | 3.12 | 3.11 |
| PyTorch | 2.10.0 + CUDA 12.8 | 2.5.1 + CUDA 12.1 |
| Key packages | transformers 5.22.1, huggingface_hub 2.x, kernels 0.17.3 | PyTorch3D, Kaolin, gsplat, flash-attn, `huggingface-hub<1.0` |

Tested on Linux x86_64, RTX 4090, NVIDIA driver 595, conda 26.7. The commands below are run from the repository root. The environments are created as conda *prefix* environments in the root, so `conda activate ./.venv-sam3` works and `.gitignore` excludes them.

## 0. Prerequisites

- conda (Miniconda or Miniforge).
- Hugging Face access to both gated repositories: request it on [facebook/sam3](https://huggingface.co/facebook/sam3) and [facebook/sam-3d-objects](https://huggingface.co/facebook/sam-3d-objects), then log in once with `hf auth login`. The token is stored in `~/.cache/huggingface/` and shared by both environments.
- On a shared conda installation, use a personal package cache (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#read-only-shared-conda-package-cache)):
  ```bash
  conda config --add pkgs_dirs ~/.conda/pkgs
  ```

## 1. `.venv-sam3`

```bash
conda create -y -p ./.venv-sam3 -c conda-forge --override-channels python=3.12 pip
conda activate ./.venv-sam3

pip install torch==2.10.0 torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -U transformers accelerate huggingface_hub opencv-python pillow matplotlib psutil tqdm ipykernel
pip install "kernels==0.17.3"   # must match the range transformers accepts, see TROUBLESHOOTING.md

python -m ipykernel install --user --name sam3 --display-name "Python (.venv-sam3)"
```

Check:
```bash
python -c "import torch, transformers; print(torch.cuda.is_available(), transformers.__version__); from transformers import Sam3VideoModel"
```

The SAM 3 weights download to `~/.cache/huggingface/hub` the first time Cell 4 runs.

## 2. `.venv-sam3d`

This follows the official [`doc/setup.md`](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md), with three fixes. Build it on a machine with the GPU attached, because PyTorch3D needs one at build time.

```bash
git clone https://github.com/facebookresearch/sam-3d-objects.git
cd sam-3d-objects

# Conda part: Python 3.11, CUDA 12.1 toolkit (nvcc), gcc 12.
# Uses `conda create` with the yml's package list instead of `conda env create`,
# to stay on conda-forge only (see TROUBLESHOOTING.md).
sed -n '/^dependencies:/,$p' environments/default.yml | grep -E '^\s+- ' | sed -E 's/^\s+- //' > /tmp/sam3d-specs.txt
conda create -y -p ../.venv-sam3d --override-channels -c conda-forge --file /tmp/sam3d-specs.txt
conda activate ../.venv-sam3d

export CUDA_HOME="$CONDA_PREFIX"        # use the env's nvcc 12.1, not a system CUDA
export TORCH_CUDA_ARCH_LIST="8.9"       # optional: compile only for your GPU (8.9 = RTX 40xx)
export MAX_JOBS=16                      # optional: limit parallel compile jobs
# The official docs also list https://pypi.ngc.nvidia.com, which no longer resolves.
export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cu121"

pip install -e '.[dev]'
pip install -e '.[p3d]'                 # PyTorch3D + flash-attn: needs the two-step install
export PIP_FIND_LINKS="https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.5.1_cu121.html"
pip install -e '.[inference]'
./patching/hydra

pip install ipykernel trimesh
python -m ipykernel install --user --name sam3d --display-name "Python (.venv-sam3d)"
cd ..
```

The full install takes about 10–15 minutes.

### Kernel environment variables (required)

`sam-3d-objects/notebook/inference.py` reads `CONDA_PREFIX`, which a Jupyter kernel does not set. Add an `env` block to `~/.local/share/jupyter/kernels/sam3d/kernel.json`, using absolute paths:

```json
"env": {
  "CONDA_PREFIX": "/abs/path/to/.venv-sam3d",
  "CUDA_HOME": "/abs/path/to/.venv-sam3d",
  "PATH": "/abs/path/to/.venv-sam3d/bin:${PATH}"
}
```

### Checkpoints (13 GB)

Download them once, outside the repository, and link them to where the notebook expects them (`sam-3d-objects/checkpoints/hf`):

```bash
hf download --repo-type model --local-dir ~/models/sam-3d-objects-download facebook/sam-3d-objects
mv ~/models/sam-3d-objects-download/checkpoints ~/models/sam-3d-objects
rm -rf ~/models/sam-3d-objects-download
ln -s ~/models/sam-3d-objects sam-3d-objects/checkpoints/hf
```

The `hf` command from `.venv-sam3` works for this. The depth model (MoGe) downloads automatically on first use.

Check (inside the activated env, from `sam-3d-objects/`):
```bash
python -c "import sys; sys.path[:0]=['notebook','.']; from inference import Inference; print('ok')"
```

## 3. VS Code

On a remote machine, the **Python** (`ms-python.python`) and **Jupyter** (`ms-toolsai.jupyter`) extensions must be installed *on the remote side*, or no kernels are listed. Then use Select Kernel → Jupyter Kernel → `Python (.venv-sam3)` or `Python (.venv-sam3d)`.

## Where large files live

| Item | Location |
|---|---|
| Hugging Face token, SAM 3 weights, cv-utils kernel | `~/.cache/huggingface/` |
| SAM 3D checkpoints | `~/models/sam-3d-objects`, linked to `sam-3d-objects/checkpoints/hf` |
| Conda package cache | `~/.conda/pkgs` |
| Jupyter kernel specs | `~/.local/share/jupyter/kernels/` |

The environments can be deleted and rebuilt without downloading the models again.
