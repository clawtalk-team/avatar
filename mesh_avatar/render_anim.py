#!/usr/bin/env python3
"""Offline animation preview of the 2.5D mesh — same warp + cross-dissolve math as
mesh_demo.html, but rasterized on CPU so we can SEE the result without WebGL.

Follows outputs/lipsync/lipsync_data.js, renders frames at FPS, muxes the audio.
    .venv-landmarks/bin/python mesh_avatar/render_anim.py [max_seconds]
writes mesh_avatar/_preview.mp4  (+ _frame_*.png samples)
"""
import json, sys, subprocess, tempfile
from pathlib import Path
from collections import Counter
import cv2, numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
M = json.loads((HERE / "mesh_data.json").read_text())
SIZE = M["size"]; TRI = np.array(M["triangles"], int); REF = M["ref"]
FPS = 25; TRANS_MS = 70
MAXS = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0

# Restrict the deforming mesh to a mouth-centered region (like the 2D demo's mouth
# mask). Keeps the feathered seam low on the face where tone differences between
# viseme stills are hidden; the rest stays as the pristine static still.
_rv = np.array(M["visemes"][REF]["verts"])[:, :2]
_mc = _rv[[13, 14, 78, 308]].mean(0)                 # mouth center
_chin = _rv[152]
_R = 1.15 * float(np.hypot(*(_chin - _mc)))          # hug mouth + chin only
TRI = np.array([t for t in TRI if np.hypot(*(_rv[t].mean(0) - _mc)) < _R])
print(f"mouth-region mesh: {len(TRI)} triangles (R={_R:.0f}px around {_mc.astype(int)})")

# timeline + audio
LIP = json.loads((REPO / "outputs/lipsync/lipsync_data.js").read_text()
                 .split("=", 1)[1].rsplit(";", 1)[0])
TL = LIP["timeline"]
AUDIO = REPO / "outputs/lipsync/audio.mp3"

# edge feather (same as shader/demo)
cnt = Counter()
for a, b, c in TRI:
    for i, j in ((a, b), (b, c), (c, a)):
        cnt[(min(i, j), max(i, j))] += 1
boundary = {v for (i, j), n in cnt.items() if n == 1 for v in (i, j)}
rv = np.array(M["visemes"][REF]["verts"])[:, :2]
N = len(rv)
ALPHA = np.ones(N); bpts = rv[list(boundary)]
for i in range(N):
    if i in boundary: ALPHA[i] = 0; continue
    d = float(np.sqrt(((bpts - rv[i]) ** 2).sum(1)).min())
    t = min(1.0, d / 46.0); ALPHA[i] = t * t * (3 - 2 * t)

# preload images + per-viseme src(uv px) and aligned dst px
IMG, SRC, DST = {}, {}, {}
for v, d in M["visemes"].items():
    im = cv2.imread(str(REPO / "outputs/flashimage" / d["file"]))
    IMG[v] = cv2.resize(im, (SIZE, SIZE)).astype(np.float32)
    SRC[v] = np.array([[u * SIZE, (1 - w) * SIZE] for u, w in d["uv"]], np.float32)
    DST[v] = np.array([[x, y] for x, y, _ in d["verts"]], np.float32)
BG = IMG[REF].copy()


def warp_onto(bg, viseme, dst_pts, gopacity):
    """Composite the forward-warped viseme straight onto bg (Delaunay tris don't
    overlap, so per-triangle 'over' is exact). Feather + global opacity via alpha."""
    img = IMG[viseme]; src = SRC[viseme]
    out = bg.copy()
    for tri in TRI:
        s = src[tri]; d = dst_pts[tri]
        x, y, w, h = cv2.boundingRect(d.astype(np.float32))
        if w <= 0 or h <= 0: continue
        dl = d - [x, y]
        Maff = cv2.getAffineTransform(s, dl.astype(np.float32))
        patch = cv2.warpAffine(img, Maff, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        tri_mask = np.zeros((h, w), np.float32)
        cv2.fillConvexPoly(tri_mask, dl.astype(np.int32), 1.0, cv2.LINE_AA)
        av = ALPHA[tri]                              # Gouraud alpha (matches WebGL vertex interp)
        try:
            P = np.array([[dl[0,0], dl[0,1], 1], [dl[1,0], dl[1,1], 1], [dl[2,0], dl[2,1], 1]], np.float64)
            A, B, C = np.linalg.solve(P, av)
            yy, xx = np.mgrid[0:h, 0:w]
            amap = np.clip(A * xx + B * yy + C, 0, 1).astype(np.float32)
        except np.linalg.LinAlgError:
            amap = np.float32(av.mean())
        a3 = (tri_mask * amap * gopacity)[..., None]
        roi = out[y:y+h, x:x+w]
        out[y:y+h, x:x+w] = patch * a3 + roi * (1 - a3)
    return out


def active(ms):
    for s in TL:
        if s["start_ms"] <= ms < s["end_ms"]:
            return s["viseme"] if s["viseme"] in M["visemes"] else REF
    return REF


smooth = lambda x: x * x * (3 - 2 * x)
dur = min(MAXS, TL[-1]["end_ms"] / 1000.0)
nframes = int(dur * FPS)
tmp = Path(tempfile.mkdtemp())
src_v = dst_v = REF; t_start = -1e9
print(f"rendering {nframes} frames @ {FPS}fps ({dur:.1f}s)…")
for f in range(nframes):
    ms = f * 1000.0 / FPS
    want = active(ms)
    if want != dst_v:
        src_v, dst_v, t_start = dst_v, want, ms
    e = smooth(min(1.0, (ms - t_start) / TRANS_MS)) if t_start > -1e8 else 1.0
    geom = DST[src_v] + (DST[dst_v] - DST[src_v]) * e
    img = warp_onto(BG, src_v, geom, 1.0)                 # source layer over still
    if dst_v != src_v:
        img = warp_onto(img, dst_v, geom, e)              # cross-dissolve target in
    cv2.imwrite(str(tmp / f"f{f:04d}.png"), np.clip(img, 0, 255).astype(np.uint8))
    if f % 25 == 0: print(f"  {f}/{nframes}")

# sample frames for quick inspection
for fr in (0, nframes // 3, 2 * nframes // 3, nframes - 1):
    p = tmp / f"f{fr:04d}.png"
    if p.exists(): cv2.imwrite(str(HERE / f"_frame_{fr:04d}.png"), cv2.imread(str(p)))

out = HERE / "_preview.mp4"
subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
                "-t", f"{dur:.2f}", "-i", str(AUDIO),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"wrote {out}")
