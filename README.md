# sam4d

Text-prompted vehicle tracking in video with **SAM 3**, followed by single-image 3D reconstruction of each vehicle with **SAM 3D Objects**.

```
input_video.mp4 ──> sam3.ipynb ──> sam3_output/ ──> sam3d.ipynb ──> sam3d_output/
                    (track "car")   frames, masks,   (3D per car)    .ply splats, .glb meshes,
                                    tracks.csv                       combined scene
```

`evaluate.ipynb` runs the same two models on a sequence with known ground truth (for example from a simulator) and measures the errors in position, orientation and size: see [docs/EVALUATION.md](docs/EVALUATION.md).

## Repository layout

```
.
├── sam3.ipynb             # Step 1: segment and track every object matching a text prompt
├── sam3d.ipynb            # Step 2: reconstruct selected objects in 3D from one frame
├── evaluate.ipynb         # Evaluation: SAM 3 + SAM 3D per frame vs ground truth
├── tools/
│   └── render_reconstruction.py  # Video of the SAM 3D reconstruction alone (real object removed)
├── sam-3d-objects/        # git submodule: Meta's SAM 3D Objects code, pinned (see below)
├── docs/
│   ├── SETUP.md           # Environment setup for both notebooks
│   ├── RELEASING.md       # How submodule updates and data releases are managed
│   ├── EVALUATION.md      # Ground-truth sequence format, metrics, how to run the evaluation
│   └── TROUBLESHOOTING.md # Known problems, causes and fixes
├── .gitmodules
└── .gitignore             # Excludes outputs, videos and environments
```

Not tracked (downloaded or generated locally): `input_video.mp4`, `sam3_output/`, `sam3d_output/`, `sequences/`, `eval_output/`, `sam-3d-objects/checkpoints/hf`.

## What is versioned where

| What | Where | How |
|---|---|---|
| Notebooks and docs | this repository | normal commits on `main` |
| SAM 3D Objects code | `sam-3d-objects/` | git submodule pinned to `f91db41` (facebookresearch/sam-3d-objects), the version the notebooks were tested with |
| Model weights | Hugging Face (gated) | downloaded locally, never committed (see [docs/SETUP.md](docs/SETUP.md)) |
| Input video + both notebooks' outputs | GitHub Releases | one release per experiment, tagged on the commit that produced it |

The release workflow and how to update the submodule are described in [docs/RELEASING.md](docs/RELEASING.md).

## How it works

### 1. `sam3.ipynb`: tracking (Hugging Face Transformers `Sam3VideoModel`)
- Loads the video (or a folder of numbered frames) at about `FPS_TARGET` frames per second, resized according to a memory preset (`low` / `medium` / `high`, chosen automatically from the available VRAM).
- Segments and tracks every object matching `PROMPTS` (default `["car"]`) through the whole clip.
- Writes `sam3_output/`:
  - `tracked_output.mp4`: overlay video
  - `tracks.csv`: one row per object per frame, with box, score, frame and mask paths
  - `frames/`, `masks/`: the raw frames and one binary mask per object per frame
  - `run_info.json`: mapping back to the original video

### 2. `sam3d.ipynb`: 3D reconstruction (Meta SAM 3D Objects)
- Picks **one frame**: `FRAME`, or by default the frame with the most objects.
- Filters that frame's objects (minimum mask area, optionally skipping objects that touch the border) and keeps the `MAX_OBJECTS` largest.
- Reconstructs each object **from that single image and mask**. Hidden sides are inferred by the model.
- Writes, for each object, `car_XXX.ply` (Gaussian splat), `car_XXX.glb` (mesh), `car_XXX_info.json` (pose) and the mask used. It can also write a combined `scene_frame_XXXXX.ply`.
- Frees the model after the reconstruction loop. Re-run Cell 4 before reconstructing again.

Files are named by object ID, so reconstructing another frame overwrites objects that appear in both.

### 3. `evaluate.ipynb`: evaluation against ground truth
- Input: a sequence folder with frames, camera intrinsics and the object's true pose per frame ([format](docs/EVALUATION.md#sequence-format)), plus the `sam3.ipynb` output for it (or the true masks).
- Reconstructs the object in **every sampled frame** (default 3 per second), saving each frame as soon as it is done, so interrupted runs resume.
- Writes per-frame metrics (`metrics.csv`), a summary, error plots, a top view of the trajectory and an overlay video of the reconstruction on the real frames.

## Quick start

1. Clone with the submodule:
   ```bash
   git clone --recurse-submodules git@github.com:alessionovel/sam4d.git
   # already cloned without it:  git submodule update --init
   ```
2. Set up the two environments and the model access: see [docs/SETUP.md](docs/SETUP.md). They have to be separate environments because their dependencies conflict.
3. Get the input video, either from the [example data](#example-data) or your own, and put it next to the notebooks as `input_video.mp4`.
4. Run `sam3.ipynb` with the `.venv-sam3` kernel, top to bottom.
5. Run `sam3d.ipynb` with the `.venv-sam3d` kernel, top to bottom.

## Example data

The [latest release](https://github.com/alessionovel/sam4d/releases/latest) always contains all the data published so far (see [docs/RELEASING.md](docs/RELEASING.md)):

| Asset | Contents |
|---|---|
| `input_video.mp4` | 1280x720 traffic video (25 fps) |
| `sam3_output.zip` | `sam3.ipynb` output for it: prompt `car`, `high` preset, 300 frames at 12.5 fps, 35 tracked cars |
| `sam3d_output.zip` | `sam3d.ipynb` output: the 5 largest cars of frame 192 (`.ply` + `.glb`) and the combined scene |
| `lap_01_slalom_*`, `lap_03_turntable_*`, `lap_02_circle_*` | ground-truth evaluation on three simulated Vadena sequences (slalom, turntable, circle): the sequences, SAM 3 outputs, `evaluate.ipynb` runs and preview videos (see [docs/EVALUATION.md](docs/EVALUATION.md)) |
| `SHA256SUMS` | checksums |

Download and unpack them in the repository root:

```bash
gh release download -R alessionovel/sam4d          # latest release
sha256sum -c SHA256SUMS
for z in *.zip; do unzip -q "$z"; done
```

With `sam3_output/` in place, `sam3d.ipynb` can be run directly, without running SAM 3 first. Splats (`.ply`) can be viewed in a Gaussian-splat viewer such as [SuperSplat](https://superspl.at/editor); meshes (`.glb`) open in Blender or any glTF viewer.

## Hardware

Measured on an RTX 4090 (24 GB), Linux:

| Step | Setting | VRAM peak | Speed |
|---|---|---|---|
| SAM 3 | `high` preset: 300 frames, 1280x720, native 1008 px | ~8–9 GB | ~2–3 frames/s |
| SAM 3D | 5 objects, 1280x720 frame | ~19 GB (13.7 GB just for the model), does not grow per object | ~1 min load, 7–14 s per object |

SAM 3D officially requires 32 GB of VRAM, but it runs on 24 GB as long as about 20 GB is free. SAM 3D Objects runs on Linux with an NVIDIA GPU only. SAM 3 also runs on Apple Silicon (MPS) or CPU, more slowly.

## Known limitations

- SAM 3D is a single-image model: each object is reconstructed from one view, and there is no fusion across frames.
- Small, distant or occluded objects give poor reconstructions. The `low` SAM 3 preset (640 px) hurts quality noticeably.
- SAM 3 memory still grows slowly with video length (~20 MB per frame), so clips much longer than 300 frames may need a lower preset.

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for problems found during setup and their fixes.

## Models and licenses

- SAM 3: [`facebook/sam3`](https://huggingface.co/facebook/sam3) (gated)
- SAM 3D Objects: [`facebook/sam-3d-objects`](https://huggingface.co/facebook/sam-3d-objects) (gated) and [github.com/facebookresearch/sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects) (included as a submodule, not modified)

Both models are released by Meta under the SAM License. The `sam-3d-objects` submodule keeps its own license.
