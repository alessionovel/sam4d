# Troubleshooting

Problems found while setting up and running the notebooks, each with its symptom, cause and fix. Versions are the ones listed in [SETUP.md](SETUP.md).

- [sam3.ipynb](#sam3ipynb)
  - [CUDA out of memory near the end of tracking](#cuda-out-of-memory-near-the-end-of-tracking)
  - ["kernels library is not installed" although it is](#kernels-library-is-not-installed-although-it-is)
- [sam3d.ipynb](#sam3dipynb)
  - [KeyError: 'CONDA_PREFIX' when importing inference](#keyerror-conda_prefix-when-importing-inference)
  - [High VRAM usage during reconstruction](#high-vram-usage-during-reconstruction)
- [Environment setup](#environment-setup)
  - [Read-only shared conda package cache](#read-only-shared-conda-package-cache)
  - [conda env create blocked by Anaconda Terms of Service](#conda-env-create-blocked-by-anaconda-terms-of-service)
  - [pip install extremely slow (dead NVIDIA index)](#pip-install-extremely-slow-dead-nvidia-index)
  - [No kernels listed in VS Code](#no-kernels-listed-in-vs-code)
  - [Harmless warnings](#harmless-warnings)

---

## sam3.ipynb

### CUDA out of memory near the end of tracking

**Status:** fixed in the notebook.

**Symptom:** Cell 5 crashes at around frame 275–281 of 300 with the `high` preset (1280x720, native 1008 px) on a 24 GB GPU:
```
OutOfMemoryError: CUDA out of memory. ... this process has 23.19 GiB memory in use.
```

**Cause:** `init_video_session(...)` was called without `inference_state_device`, which then defaults to the inference device (the GPU). SAM 3 keeps every tracked object's per-frame state (`output_dict_per_obj`: memory features and masks) and never frees old frames. GPU memory therefore grows with frames × objects.

**Fix:** keep that state in system RAM.
```python
session = processor.init_video_session(
    video=frames,
    inference_device=DEVICE,
    inference_state_device="cpu",
    processing_device="cpu",
    video_storage_device="cpu",
    dtype=DTYPE,
)
```
Cell 1 also sets `PYTORCH_ALLOC_CONF=expandable_segments:True` before importing torch, which reduces fragmentation.

**Result:** the same 300-frame run completes with a peak of 8.1 GB allocated (8.8 GB reserved), and runs faster (about 2–3 frames/s instead of 1.5). Memory still grows slowly, about 16–25 MB per frame, so much longer clips may still need a lower preset.

**Notes:**
- After an OOM error, **restart the kernel**. Cell 7 ("Free memory") is not enough, because the stored traceback keeps the tensors alive.
- A crashed run leaves `sam3_output/` inconsistent. `frames/` and `masks/` are written during the loop, while `tracks.csv` and `run_info.json` are written only at the end. Don't feed it to `sam3d.ipynb`.

### "kernels library is not installed" although it is

**Symptom:**
```
[transformers] kernels library is not installed. NMS post-processing, hole filling, and sprinkle removal will be skipped.
```

**Cause:** transformers 5.22.1 only accepts `kernels` from version 0.17.2 up to, but not including, 0.18.0 (`KERNELS_MIN_VERSION` / `KERNELS_MAX_VERSION` in `transformers/utils/import_utils.py`). A plain `pip install kernels` installs 0.18.1, which transformers reports as "not installed".

**Why it matters:** without it, SAM 3 skips mask post-processing. NMS (non-maximum suppression) removes duplicate detections, so the same car doesn't get two IDs; the other steps fill holes and remove specks from masks. Both improve the input to SAM 3D.

**Fix:** `pip install "kernels==0.17.3"`, then restart the kernel. The check happens when transformers is first imported. After upgrading transformers, check the new allowed range:
```bash
grep "KERNELS_M.._VERSION =" .venv-sam3/lib/python3.12/site-packages/transformers/utils/import_utils.py
```

---

## sam3d.ipynb

### KeyError: 'CONDA_PREFIX' when importing inference

**Symptom:** `from inference import Inference` (Cell 4) fails with `KeyError: 'CONDA_PREFIX'`.

**Cause:** `sam-3d-objects/notebook/inference.py` runs `os.environ["CUDA_HOME"] = os.environ["CONDA_PREFIX"]`, which only works in an activated conda env. Jupyter kernels don't activate the env.

**Fix:** set `CONDA_PREFIX`, `CUDA_HOME` and `PATH` in the kernel spec ([SETUP.md](SETUP.md#kernel-environment-variables-required)).

### High VRAM usage during reconstruction

**Symptom:** VRAM jumps from ~14 GB (model loaded) to ~22 GB during Cell 5, as reported by `nvidia-smi`.

**Explanation:** this is expected, not a leak:
- about 13.7 GB is the model itself;
- each object temporarily needs about 5 GB more while it's being computed (18.7 GB peak measured for one object);
- the rest is PyTorch's allocator cache, which is reused for the next object.

Calling `torch.cuda.empty_cache()` between objects wouldn't lower the peak, and it would let other processes take memory the next object needs.

**Change in the notebook:** Cell 5 frees the model and the cache after the last object, so the GPU is released for the rest of the notebook. Re-run Cell 4 before reconstructing again.

---

## Environment setup

### Read-only shared conda package cache

**Symptom:** `conda create` fails with `sqlite3.OperationalError: attempt to write a readonly database`.

**Cause:** a shared conda install whose package cache (e.g. `/opt/miniconda3/pkgs`) is not writable for your user.

**Fix:** `conda config --add pkgs_dirs ~/.conda/pkgs`

### conda env create blocked by Anaconda Terms of Service

**Symptom:** `CondaToSNonInteractiveError: Terms of Service have not been accepted for the following channels: https://repo.anaconda.com/pkgs/main ...`

**Cause:** the `.condarc` lists the `defaults` channel, and `conda env create` has no `--override-channels` option. SAM 3D's `environments/default.yml` only needs conda-forge.

**Fix:** pass the yml's package list to `conda create --override-channels -c conda-forge` instead ([SETUP.md](SETUP.md#2-venv-sam3d)). No Terms of Service acceptance is needed.

### pip install extremely slow (dead NVIDIA index)

**Symptom:** `pip install -e '.[dev]'` in `sam-3d-objects` takes many minutes and never finishes. The log is full of `Retrying ... NewConnectionError ... Name or service not known`.

**Cause:** the official instructions set `PIP_EXTRA_INDEX_URL="https://pypi.ngc.nvidia.com https://download.pytorch.org/whl/cu121"`, but `pypi.ngc.nvidia.com` no longer resolves. pip retries it several times for every package.

**Fix:** `export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cu121"`. The full install then takes about 11 minutes.

### No kernels listed in VS Code

**Cause:** with VS Code Remote, extensions are installed per host. The remote server had no Python or Jupyter extension.

**Fix:** install `ms-python.python` and `ms-toolsai.jupyter` on the remote host, then run "Developer: Reload Window".

### Harmless warnings

In `.venv-sam3d`:
- `pip check` reports `bpy`, `decord` and `bitsandbytes` as "not supported on this platform". This is a pip quirk; all three import correctly.
- `hf-gradio` requires `gradio-client>=2`. This only affects the Gradio demo, not the notebook.

In `.venv-sam3`:
- `TqdmWarning: IProgress not found`: progress bars are shown as text. You can install `ipywidgets` for graphical bars.
- `memory_attention_rope_theta is deprecated`: comes from the model config and is harmless.
