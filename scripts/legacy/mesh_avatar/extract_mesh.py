#!/usr/bin/env python3
"""
2.5D mesh extractor (SEPARATE prototype — does not touch scripts/extract_landmarks.py
or the working morph_demo.html pipeline).

For each viseme still in outputs/flashimage/manifest.json:
  1. MediaPipe Face Landmarker -> 478 landmarks WITH z (depth) + the 52 ARKit
     blendshapes + the facial transformation matrix.
  2. Similarity-align each frame's (x,y) to the reference (sil) on stable points
     so the head stays put and only the mouth/face deforms.
  3. Delaunay-triangulate the reference face points (NO full-frame border — we want a
     face *mesh*, not a warped rectangle).

Why blendshapes too? MediaPipe's 52-category set is the SAME vocabulary Audio2Face
emits, so storing them here proves the "A2F can drive this rig later" bridge.

Output: mesh_avatar/mesh_data.json
  {
    "size": 512,
    "ref": "sil",
    "texture": "../outputs/flashimage/sil.png",
    "triangles": [[i,j,k], ...],          # over the 478 face verts
    "blendshape_names": ["_neutral", "browDownLeft", ...],
    "visemes": {
      "sil": {
        "verts": [[x,y,z], ...],          # 478 aligned 3D verts, canvas units
        "blendshapes": [0.0, 0.12, ...],  # 52 ARKit weights (may be empty)
      }, ...
    }
  }

Run with the existing landmarks venv (MediaPipe needs Python <=3.12):
    .venv-landmarks/bin/python mesh_avatar/extract_mesh.py
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
OUT = Path(__file__).resolve().parent / "mesh_data.json"
SIZE = 512

# Stable landmarks for alignment — rigid under speech (eyes, nose bridge, forehead,
# temples). Excludes chin/jaw which drop when the mouth opens.
STABLE = [33, 133, 362, 263, 1, 168, 6, 10, 234, 454]


def similarity(src, dst, idx):
    """Least-squares 2D similarity (scale+rot+trans) mapping src(x,y)->dst over idx."""
    s, d = src[idx], dst[idx]
    ms, md = s.mean(0), d.mean(0)
    a, b = s - ms, d - md
    num_re = float((a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1]).sum())
    num_im = float((a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum())
    den = float((a ** 2).sum()) or 1e-9
    c_re, c_im = num_re / den, num_im / den
    dx = md[0] - (c_re * ms[0] - c_im * ms[1])
    dy = md[1] - (c_im * ms[0] + c_re * ms[1])
    return np.array([[c_re, -c_im, dx], [c_im, c_re, dy]], dtype=np.float64)


def apply_xy(m, pts3):
    """Apply 2x3 similarity to (x,y); leave z untouched (depth scale handled in JS)."""
    out = pts3.copy()
    out[:, 0] = m[0, 0] * pts3[:, 0] + m[0, 1] * pts3[:, 1] + m[0, 2]
    out[:, 1] = m[1, 0] * pts3[:, 0] + m[1, 1] * pts3[:, 1] + m[1, 2]
    return out


def detect(fm, png_path):
    img = cv2.imread(str(png_path))
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    res = fm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_landmarks:
        return None
    lm = res.face_landmarks[0]
    # x,y scaled to canvas; z is normalized roughly to image width -> scale by SIZE too.
    verts = np.array([[p.x * SIZE, p.y * SIZE, p.z * SIZE] for p in lm], dtype=np.float64)
    bs = res.face_blendshapes[0] if res.face_blendshapes else []
    names = [c.category_name for c in bs]
    weights = [round(float(c.score), 4) for c in bs]
    return verts, names, weights


def main():
    manifest = json.loads((DIR / "manifest.json").read_text())
    visemes = manifest.get("visemes", {})
    if not visemes:
        raise SystemExit("No visemes in manifest.json — run flashimage_generate.py first.")

    opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )

    raw, bs_names = {}, []
    with vision.FaceLandmarker.create_from_options(opts) as fm:
        for v, fname in visemes.items():
            r = detect(fm, DIR / fname)
            if r is None:
                print(f"[{v}] no face detected — skipping")
                continue
            verts, names, weights = r
            if names and not bs_names:
                bs_names = names
            raw[v] = (fname, verts, weights)
            print(f"[{v}] {len(verts)} verts, {len(weights)} blendshapes")

    if not raw:
        raise SystemExit("Face detection failed on every still.")

    ref = "sil" if "sil" in raw else next(iter(raw))
    ref_verts = raw[ref][1]
    stable = np.array(STABLE, dtype=int)

    out = {
        "size": SIZE,
        "ref": ref,
        "texture": f"../outputs/flashimage/{raw[ref][0]}",
        "blendshape_names": bs_names,
        "visemes": {},
    }
    for v, (fname, verts, weights) in raw.items():
        m = np.array([[1, 0, 0], [0, 1, 0]], float) if v == ref \
            else similarity(verts[:, :2], ref_verts[:, :2], stable)
        aligned = apply_xy(m, verts)
        out["visemes"][v] = {
            "file": fname,
            # aligned 3D verts -> geometry positions (head stays put, only face deforms)
            "verts": [[round(float(x), 2), round(float(y), 2), round(float(z), 2)]
                      for x, y, z in aligned],
            # RAW (unaligned) landmark UVs into THIS viseme's own image, so we texture
            # each frame with its own teeth/interior instead of stretching sil.
            "uv": [[round(float(x) / SIZE, 5), round(1.0 - float(y) / SIZE, 5)]
                   for x, y in verts[:, :2]],
            "blendshapes": weights,
        }

    # Triangulate the reference face verts in 2D (x,y); reuse for every viseme.
    tri = Delaunay(ref_verts[:, :2])
    out["triangles"] = [[int(a), int(b), int(c)] for a, b, c in tri.simplices]
    print(f"ref={ref}  verts={len(ref_verts)}  triangles={len(out['triangles'])}  "
          f"blendshapes={len(bs_names)}")

    OUT.write_text(json.dumps(out))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
