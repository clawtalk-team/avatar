#!/usr/bin/env python3
"""Offline sanity render of the 2.5D mesh, so we can SEE what WebGL should show
(headless Chromium has no WebGL). Forward-warps a viseme's own image (uv space)
onto its aligned geometry, per-triangle affine, with the same edge feather.

    .venv-landmarks/bin/python mesh_avatar/debug_render.py
writes mesh_avatar/_debug_{sil,aa,O}.png
"""
import json
from pathlib import Path
import cv2, numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
M = json.loads((HERE / "mesh_data.json").read_text())
SIZE = M["size"]; TRI = np.array(M["triangles"], int); REF = M["ref"]

# edge feather (same logic as the shader)
from collections import Counter
cnt = Counter()
for a, b, c in TRI:
    for i, j in ((a, b), (b, c), (c, a)):
        cnt[(min(i, j), max(i, j))] += 1
boundary = {v for (i, j), n in cnt.items() if n == 1 for v in (i, j)}
rv = np.array(M["visemes"][REF]["verts"])[:, :2]
N = len(rv)
alpha = np.ones(N)
bpts = rv[list(boundary)]
for i in range(N):
    if i in boundary:
        alpha[i] = 0; continue
    d = np.sqrt(((bpts - rv[i]) ** 2).sum(1)).min()
    a = min(1.0, d / 46.0); alpha[i] = a * a * (3 - 2 * a)


def warp(viseme):
    v = M["visemes"][viseme]
    img = cv2.imread(str(REPO / "outputs" / "flashimage" / v["file"]))
    img = cv2.resize(img, (SIZE, SIZE))
    src = np.array([[u * SIZE, (1 - w) * SIZE] for u, w in v["uv"]], np.float32)  # uv->px
    dst = np.array([[x, y] for x, y, _ in v["verts"]], np.float32)                # aligned px
    out = np.zeros((SIZE, SIZE, 3), np.uint8)
    acc = np.zeros((SIZE, SIZE), np.float32)
    for tri in TRI:
        s = src[tri]; d = dst[tri]
        r = cv2.boundingRect(d.astype(np.float32))
        x, y, w, h = r
        if w <= 0 or h <= 0:
            continue
        dl = d - [x, y]
        Maff = cv2.getAffineTransform(s.astype(np.float32), dl.astype(np.float32))
        patch = cv2.warpAffine(img, Maff, (w, h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REFLECT)
        mask = np.zeros((h, w), np.float32)
        cv2.fillConvexPoly(mask, dl.astype(np.int32), 1.0, cv2.LINE_AA)
        # per-vertex alpha -> barycentric-ish: use mean of triangle's vertex alphas
        ta = float(alpha[tri].mean())
        mask *= ta
        roi = out[y:y+h, x:x+w].astype(np.float32)
        a3 = mask[..., None]
        out[y:y+h, x:x+w] = (patch * a3 + roi * (1 - a3)).astype(np.uint8)
        acc[y:y+h, x:x+w] = np.maximum(acc[y:y+h, x:x+w], mask)
    return out, acc


bg = cv2.imread(str(REPO / "outputs" / "flashimage" / M["visemes"][REF]["file"]))
bg = cv2.resize(bg, (SIZE, SIZE))
for vis in ["sil", "aa", "O"]:
    face, acc = warp(vis)
    a3 = np.clip(acc, 0, 1)[..., None]
    comp = (face * a3 + bg * (1 - a3)).astype(np.uint8)
    cv2.imwrite(str(HERE / f"_debug_{vis}.png"), comp)
    print(f"wrote _debug_{vis}.png")
print("done")
