# sam4d

Text-prompted vehicle tracking in video with **SAM 3**, followed by single-image 3D reconstruction of each vehicle with **SAM 3D Objects**.

```
input_video.mp4 ──> sam3.ipynb ──> sam3_output/ ──> sam3d.ipynb ──> sam3d_output/
                    (track "car")   frames, masks,   (3D per car)    .ply splats, .glb meshes,
                                    tracks.csv                       combined scene
```

## Repository layout

```
.
├── sam3.ipynb             # Step 1: segment and track every object matching a text prompt
├── sam3d.ipynb            # Step 2: reconstruct selected objects in 3D from one frame
├── docs/
│   ├── SETUP.md           # Environment setup for both notebooks
│   └── TROUBLESHOOTING.md # Known problems, causes and fixes
└── .gitignore             # Excludes outputs, videos, the cloned sam-3d-objects repo, envs
```

Not tracked (generated locally): `input_video.mp4`, `sam3_output/`, `sam3d_output/`, `sam-3d-objects/`.

## How it works

### 1. `sam3.ipynb`: tracking (Hugging Face Transformers `Sam3VideoModel`)
- Loads the video at about `FPS_TARGET` frames per second, resized according to a memory preset (`low` / `medium` / `high`, chosen automatically from the available VRAM).
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

## Quick start

1. Set up the two environments and the model access: see [docs/SETUP.md](docs/SETUP.md). They have to be separate environments because their dependencies conflict.
2. Put the video next to the notebooks as `input_video.mp4`.
3. Run `sam3.ipynb` with the `.venv-sam3` kernel, top to bottom.
4. Run `sam3d.ipynb` with the `.venv-sam3d` kernel, top to bottom.

## Example data

Release [`v0.1.0`](https://github.com/alessionovel/sam4d/releases/tag/v0.1.0) contains the input video and the outputs of both notebooks for it, produced with the notebook versions at that tag:

| Asset | Contents |
|---|---|
| `input_video.mp4` | 1280x720 traffic video (25 fps) |
| `sam3_output.zip` | `sam3.ipynb` output: prompt `car`, `high` preset, 300 frames at 12.5 fps, 35 tracked cars |
| `sam3d_output.zip` | `sam3d.ipynb` output: the 5 largest cars of frame 192 (`.ply` + `.glb`) and the combined scene |
| `SHA256SUMS` | checksums |

Download and unpack them in the repository root:

```bash
gh release download v0.1.0 -R alessionovel/sam4d
sha256sum -c SHA256SUMS
unzip -q sam3_output.zip && unzip -q sam3d_output.zip
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
- SAM 3D Objects: [`facebook/sam-3d-objects`](https://huggingface.co/facebook/sam-3d-objects) (gated) and [github.com/facebookresearch/sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects)

Both models are released by Meta under the SAM License.
