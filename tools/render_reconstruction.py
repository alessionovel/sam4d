"""Video of SAM 3D reconstructions alone: the original frame next to the same frame with the real object removed
and the reconstruction drawn in its place (static camera; known-camera evaluate.ipynb runs).

Usage: python tools/render_reconstruction.py eval_output/<run> out.mp4 [--fps 30] [--sequence sequences/<name>]
"""
import argparse, json, glob
from pathlib import Path
import numpy as np, cv2

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("eval_dir", help="an evaluate.ipynb output folder (summary.json + reconstructions/)")
ap.add_argument("out", help="output .mp4")
ap.add_argument("--fps", type=float, default=3)
ap.add_argument("--sequence", help="sequence folder (default: the one recorded in summary.json)")
a = ap.parse_args()
ev, out, fps = Path(a.eval_dir), Path(a.out), a.fps
S = json.load(open(ev / "summary.json"))
seq = Path(a.sequence or S["sequence"]); C = np.array(S["axis_alignment_sam3d_to_object"])
cam = json.load(open(seq / "camera.json")); K = np.array(cam["K"], float)
FLIP = np.diag([-1.0, -1.0, 1.0])


def quat_to_R(w, x, y, z):           # same as pytorch3d.transforms.quaternion_to_matrix
    n = 2 / (w * w + x * x + y * y + z * z)
    return np.array([[1 - n * (y * y + z * z), n * (x * y - z * w), n * (x * z + y * w)],
                     [n * (x * y + z * w), 1 - n * (x * x + z * z), n * (y * z - x * w)],
                     [n * (x * z - y * w), n * (y * z + x * w), 1 - n * (x * x + y * y)]])


def rgb(f): return cv2.imread(str(seq / "rgb" / f"{f:06d}.png"))
def gtmask(f):
    p = seq / "masks" / f"{f:06d}.png"
    return cv2.imread(str(p), 0) > 127 if p.exists() else None


files = sorted(glob.glob(str(ev / "reconstructions" / "frame_*.npz")))
frames = [int(Path(p).stem.split("_")[1]) for p in files]
H, W = rgb(frames[0]).shape[:2]

# Empty background: per-pixel median over sequence frames where the car is not there; inpaint what's never free
allf = sorted(int(Path(p).stem) for p in glob.glob(str(seq / "rgb" / "*.png")))
lo, hi = min(frames), max(frames)
pool = [f for f in allf if lo - 300 <= f <= hi + 300]
pool = pool[:: max(1, len(pool) // 60)]
stack = np.zeros((len(pool), H, W, 3), np.uint8); free = np.zeros((len(pool), H, W), bool)
for i, f in enumerate(pool):
    stack[i] = rgb(f); m = gtmask(f)
    free[i] = True if m is None else ~cv2.dilate(m.astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool)
data = np.where(free[..., None], stack.astype(np.float32), np.nan)
bg = np.nanmedian(data, axis=0); never = np.isnan(bg[..., 0]); bg = np.nan_to_num(bg).astype(np.uint8)
del data, stack
print(f"background from {len(pool)} frames; {never.mean():.1%} of pixels never free")


def clean_plate(f):
    img = rgb(f).copy(); m = gtmask(f)
    if m is None:
        return img
    m = cv2.dilate(m.astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool)
    img[m & ~never] = bg[m & ~never]
    hole = (m & never).astype(np.uint8)
    return cv2.inpaint(img, hole, 7, cv2.INPAINT_TELEA) if hole.any() else img


vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H // 2))
for p, f in zip(files, frames):
    d = np.load(p)
    M = FLIP @ quat_to_R(*d["quat_wxyz"]).T; s = float(d["scale"][0]); t = FLIP @ d["translation"]
    pts = (C @ (s * d["xyz_local"].astype(float)).T).T
    lo3, hi3 = np.percentile(pts, [1, 99], axis=0); c_obj = (lo3 + hi3) / 2
    Rp = M @ C.T; pc = (Rp @ (pts - c_obj).T).T + Rp @ c_obj + t
    col = (d["rgb"].astype(float) * (255 if d["rgb"].max() <= 1 else 1)).astype(np.uint8)[:, ::-1]
    # focal SAM 3D implicitly used (as in evaluate.ipynb), so the reconstruction covers its mask
    mk = np.unpackbits(d["mask"])[: int(np.prod(d["mask_shape"]))].reshape(d["mask_shape"]).astype(bool)
    ys, xs = np.where(mk); v = pc[pc[:, 2] > 0.01]
    fe = np.mean([np.ptp(xs) / np.ptp(v[:, 0] / v[:, 2]), np.ptp(ys) / np.ptp(v[:, 1] / v[:, 2])])
    Ke = np.array([[fe, 0, K[0, 2]], [0, fe, K[1, 2]], [0, 0, 1]])
    order = np.argsort(-pc[:, 2]); pc, col = pc[order], col[order]
    ok = pc[:, 2] > 0.01; pc, col = pc[ok], col[ok]
    uv = (Ke @ (pc / pc[:, 2:3]).T).T[:, :2]
    r = max(2, int(round(0.4 * fe * (s / 64) / np.median(pc[:, 2]))))
    img = clean_plate(f)
    for (u, v_), c in zip(np.round(uv).astype(int), col):
        if 0 <= u < W and 0 <= v_ < H:
            cv2.circle(img, (u, v_), r, tuple(int(x) for x in c), -1, cv2.LINE_AA)
    left = rgb(f)
    for im, label in ((left, "original"), (img, "SAM 3D reconstruction (car removed)")):
        cv2.putText(im, label, (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 5, cv2.LINE_AA)
    cv2.putText(left, f"frame {f}", (30, H - 40), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 4, cv2.LINE_AA)
    vw.write(np.hstack([cv2.resize(left, (W // 2, H // 2)), cv2.resize(img, (W // 2, H // 2))]))
    if f == frames[len(frames) // 2]:
        cv2.imwrite(str(out.with_suffix(".jpg")), img)
vw.release(); print("saved", out)
