# Evaluation against ground truth

`evaluate.ipynb` measures how well SAM 3 + SAM 3D Objects recover **one object's position, orientation and size** in a sequence filmed by a **static, calibrated camera** whose ground truth is known (for example a recording from a simulator).

```
sequence/rgb/ ──> sam3.ipynb ──> eval_output/sam3_<seq>/ ──┐
                                                           ├──> evaluate.ipynb ──> eval_output/<seq>_sam3/
sequence/ (camera.json, gt.csv, masks/) ───────────────────┘
```

With `MASK_SOURCE = "gt"`, `evaluate.ipynb` gives SAM 3D the ground-truth masks instead, which tests SAM 3D on its own.

## Sequence format

One folder per sequence. Put it (or a link to it) in `sequences/`, which git ignores:

```
sequences/<name>/
├── rgb/          000000.png, 000001.png, ...   frames, named by frame number
├── masks/        000000.png, ...               optional: true object mask (255 = object); a missing file = empty mask
├── camera.json   intrinsics, optional world pose
├── gt.csv        one row per frame: the object's pose in the camera frame
└── traj.json     optional: only read for the object size (CARLA's `bbox_extent`)
```

### `camera.json`

```json
{
  "width": 1920, "height": 1080,
  "K": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
  "world": {                                   // optional ("rh_world" is accepted too)
    "position_m": [x, y, z],
    "R_world_from_cam_opencv": [[...], [...], [...]]
  }
}
```

An ideal pinhole camera (no distortion). The world frame must be right-handed with z up; it is only used for the heading error and the trajectory plot.

### `gt.csv`

| Column | Required | Meaning |
|---|---|---|
| `frame` | yes | frame number (= file name in `rgb/`) |
| `cam_x`, `cam_y`, `cam_z` | yes | object centre (centre of its 3D box) in the camera frame, metres |
| `cam_qx`, `cam_qy`, `cam_qz`, `cam_qw` | yes | rotation object → camera |
| `sim_time_s` or `time_s` | no | time, used to get the frame rate |
| `visibility` | no | only `visible` frames are evaluated |
| `truncated` | no | 1 if the object is cut by the image border |
| `mask_frac` | no | mask area / image area (computed from `masks/` if missing) |

Conventions:
- **camera frame:** OpenCV, x right, y down, z forward;
- **object frame:** origin at the centre of the object's 3D box, x forward, y left, z up;
- **quaternions:** Hamilton, `(qx, qy, qz, qw)`, mapping object coordinates into camera coordinates: `p_cam = R(q) p_obj + t`.

The object size (length, width, height of the box) is set with `OBJECT_SIZE_LWH` in the notebook, or read from `traj.json` if present.

## Running it

1. **SAM 3** (`sam3.ipynb`, kernel `.venv-sam3`). In Cell 2:
   ```python
   VIDEO_PATH = "sequences/<name>/rgb"     # a folder of frames works like a video
   FOLDER_FPS = 30                         # the sequence's frame rate
   FPS_TARGET = 3                          # frames per second to evaluate
   PRESET = "high"
   OVERRIDES = {"MAX_WIDTH": 1920}         # keep the native resolution
   OUTPUT_DIR = "./eval_output/sam3_<name>"
   ```
2. **Evaluation** (`evaluate.ipynb`, kernel `.venv-sam3d`). In Cell 1: `SEQUENCE_DIR`, `MASK_SOURCE = "sam3"`, `SAM3_OUTPUT_DIR` = the folder above. Run all cells.

### Camera given to SAM 3D (`CAMERA_MODE`)

- `"estimate"` (default): SAM 3D runs as released. MoGe estimates depth and focal length from the image alone, so the object's distance and metric size can be far off (see Scale below).
- `"known"`: SAM 3D gets the true camera. The notebook runs MoGe with the true horizontal field of view, scales its depth to metres using the ground plane (pixels of the ground around the object, whose true depth follows from the camera pose and `GROUND_Z`), back-projects it with the true intrinsics and passes that pointmap to SAM 3D. Needs the camera's world pose. The ground height is read from `GROUND_Z`, `camera.json`/`traj.json` (`ground_z`), or estimated from the ground-truth box (median centre height minus half the box height).

On the Vadena slalom (lap_01, 20 frames) the median centre error drops from 10.4 m (`estimate`) to 0.24 m (`known`), and the size from 0.34 x 0.18 x 0.12 m to 2.76 x 1.50 x 0.95 m (true 2.90 x 1.51 x 1.15 m). The rotation error does not change.

Each frame's reconstruction is saved as soon as it's done. If the run stops (out of memory on a shared GPU, kernel restart), run the cells again: finished frames are skipped (`RESUME = True`). Frames that run out of GPU memory are retried a few times (`OOM_RETRIES`).

Time on an RTX 4090: SAM 3 about 1 s per frame at 1920x1080; SAM 3D about 1 min to load, then ~7 s per frame. 76 frames take about 12 minutes in total.

## Outputs (`eval_output/<name>_<mask source>/`)

| File | Contents |
|---|---|
| `metrics.csv` | one row per frame, all metrics below |
| `summary.json` | settings, mean/median/min/max of each metric, the axis alignment used |
| `errors.png` | metrics over the frames |
| `trajectory_top.png` | true vs predicted centre and heading, seen from above (needs the world pose) |
| `overlay.mp4` | the reconstruction drawn over the real frames, with the true (green) and predicted (magenta) boxes |
| `reconstructions/frame_NNNNNN.npz` | per frame: SAM 3D pose (`quat_wxyz`, `translation`, `scale`), a subsample of the object's points and colours in SAM 3D's object coordinates, the mask used |

To see the reconstruction alone, `tools/render_reconstruction.py` writes a video with the original frame on the left and, on the right, the same frame with the real object removed (background taken from other frames of the sequence, inpainted where the object never moves away) and the reconstruction drawn in its place:

```bash
.venv-sam3d/bin/python tools/render_reconstruction.py eval_output/<run> reconstruction.mp4 --fps 30
```

## Metrics

| Metric | Meaning |
|---|---|
| `mask_iou` | SAM 3 mask vs true mask (`sam3` only). When SAM 3 finds several objects, the one overlapping the true object most is used; the others are counted as extra detections |
| `trans_err_m` | distance between predicted and true centre, metres |
| `depth_err_m` | predicted minus true depth (camera z); negative = too close |
| `lateral_err_m` | centre error perpendicular to the viewing ray |
| `rot_err_deg` | orientation error after the axis alignment (below) |
| `heading_err_deg` | error of the forward direction on the ground plane |
| `L/W/H_pred_m` | size of the reconstruction along the object's axes (1st-99th percentile of its points) |
| `scale_corr` | true distance / predicted distance |
| `L/W/H_scaled_m` | size × `scale_corr`: the size once the reconstruction is moved to the true distance |
| `focal_ratio` | focal length SAM 3D implicitly used / true focal length |
| `reproj_iou` | reconstruction projected with the true intrinsics vs true mask |
| `reproj_iou_own_focal` | same with SAM 3D's own focal length: how well the reconstruction explains the mask |

### How the comparison works

**Pose conversion.** SAM 3D returns a quaternion `q` (w, x, y, z), a translation `t` and a scale `s` that place its object points in a PyTorch3D camera frame (x left, y up, z forward), as row vectors: `p = (s·p_obj) @ R(q) + t`. In the OpenCV camera frame this is `p_cv = F R(q)ᵀ (s·p_obj) + F t`, with `F = diag(-1, -1, 1)`. The notebook checks this formula against PyTorch3D before using it.

**Axis alignment.** SAM 3D chooses its own axes for the object, not the ground truth's (x forward, y left, z up). The notebook estimates a single rotation from SAM 3D's axes to the object's, as the robust mean over all evaluated frames, and uses it for every frame. The rotation error is therefore measured after this one alignment. It shows how consistent the orientation is across frames: a 180° error means the front and back were swapped. Because the alignment is fitted on the same frames, very short sequences (a handful of frames) give optimistic rotation errors.

**Scale.** With `CAMERA_MODE = "estimate"`, SAM 3D estimates depth and the camera intrinsics itself, using MoGe, and is not given the true camera. From one image it can't tell a small, close object from a large, distant one. Its metric scale and distance can therefore be far off, while the position in the image and the shape are right. `scale_corr` and `L/W/H_scaled_m` separate the two effects. Once the reconstruction is moved to the true distance, any remaining size error mostly comes from the focal length SAM 3D assumed (`focal_ratio`).
