#!/usr/bin/env python3
"""
Precompute MediaPipe face landmarks + alignment + triangulation for the viseme
stills, so the browser demo can do pure canvas-2D morphing (no WebGL, no CDN,
no per-load detection cost).

For each still in outputs/flashimage/manifest.json:
  1. MediaPipe FaceMesh (refine_landmarks=True) -> 478 landmarks.
  2. Similarity-align each still to the reference (sil) using stable points
     (eyes/nose/contour) so only the mouth differs frame-to-frame.
  3. Append fixed border anchor points and Delaunay-triangulate the reference.

Output: outputs/flashimage/geometry.json
  {
    "size": 512, "ref": "sil",
    "triangles": [[i,j,k], ...],
    "visemes": { "sil": {"file":"sil.png","xform":[a,b,c,d,e,f],"points":[[x,y],...]} }
  }

Run with the dedicated venv (MediaPipe needs Python <=3.12):
    .venv-landmarks/bin/python scripts/extract_landmarks.py
"""
import json
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from scipy.spatial import Delaunay

REPO = Path(__file__).resolve().parent.parent
DIR = REPO / "outputs" / "flashimage"
MODEL = REPO / "models" / "face_landmarker.task"
SIZE = 512
# Stable landmarks drive alignment — must be RIGID under speech: eyes, nose bridge,
# forehead, upper cheeks. Deliberately excludes the chin (152) and anything on the
# jaw, which drop when the mouth opens and would make the aligner rescale the frame.
STABLE = [33, 133, 362, 263, 1, 168, 6, 10, 234, 454]


def border_points():
    pts = []
    for i in range(5):
        p = i * SIZE / 4
        pts += [[p, 0.0], [p, float(SIZE)], [0.0, p], [float(SIZE), p]]
    return pts


def similarity(src, dst, idx):
    """Least-squares 2D similarity (scale+rot+trans) mapping src->dst over idx.
    Returns canvas matrix [a,b,c,d,e,f] for setTransform."""
    s = src[idx]
    d = dst[idx]
    ms, md = s.mean(0), d.mean(0)
    a = s - ms
    b = d - md
    num_re = float((a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1]).sum())
    num_im = float((a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum())
    den = float((a ** 2).sum()) or 1e-9
    c_re, c_im = num_re / den, num_im / den
    dx = md[0] - (c_re * ms[0] - c_im * ms[1])
    dy = md[1] - (c_im * ms[0] + c_re * ms[1])
    return [c_re, c_im, -c_im, c_re, float(dx), float(dy)]


def apply_xform(m, pts):
    a, b, c, d, e, f = m
    out = np.empty_like(pts)
    out[:, 0] = a * pts[:, 0] + c * pts[:, 1] + e
    out[:, 1] = b * pts[:, 0] + d * pts[:, 1] + f
    return out


def detect(landmarker, png_path):
    img = cv2.imread(str(png_path))
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res = landmarker.detect(mp_img)
    if not res.face_landmarks:
        return None
    lm = res.face_landmarks[0]
    # scale normalized coords to the SIZE x SIZE canvas the demo draws into
    return np.array([[p.x * SIZE, p.y * SIZE] for p in lm], dtype=np.float64)


def main():
    manifest = json.loads((DIR / "manifest.json").read_text())
    visemes = manifest.get("visemes", {})
    if not visemes:
        raise SystemExit("No visemes in manifest.json — run flashimage_generate.py first.")

    opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)),
        running_mode=vision.RunningMode.IMAGE, num_faces=1)
    raw = {}
    with vision.FaceLandmarker.create_from_options(opts) as fm:
        for v, fname in visemes.items():
            pts = detect(fm, DIR / fname)
            if pts is None:
                print(f"[{v}] no face detected — skipping")
                continue
            raw[v] = (fname, pts)
            print(f"[{v}] {len(pts)} landmarks")

    if not raw:
        raise SystemExit("Face detection failed on every still.")
    ref = "sil" if "sil" in raw else next(iter(raw))
    ref_pts = raw[ref][1]
    border = np.array(border_points(), dtype=np.float64)
    stable = np.array(STABLE, dtype=int)

    out = {"size": SIZE, "ref": ref, "visemes": {}}
    aligned_ref_full = None
    for v, (fname, pts) in raw.items():
        m = [1, 0, 0, 1, 0, 0] if v == ref else similarity(pts, ref_pts, stable)
        aligned = apply_xform(m, pts)
        full = np.vstack([aligned, border])
        out["visemes"][v] = {
            "file": fname,
            "xform": [round(x, 5) for x in m],
            "points": [[round(float(x), 2), round(float(y), 2)] for x, y in full],
        }
        if v == ref:
            aligned_ref_full = full

    tri = Delaunay(aligned_ref_full)
    out["triangles"] = [[int(a), int(b), int(c)] for a, b, c in tri.simplices]
    print(f"ref={ref}  points/frame={len(aligned_ref_full)}  triangles={len(out['triangles'])}")

    (DIR / "geometry.json").write_text(json.dumps(out))
    print(f"wrote {DIR / 'geometry.json'}")


if __name__ == "__main__":
    main()
