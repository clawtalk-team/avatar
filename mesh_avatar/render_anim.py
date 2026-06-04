#!/usr/bin/env python3
"""Offline animation preview of the 2.5D mesh — same warp + cross-dissolve math as
mesh_demo.html, rasterized on CPU so we can SEE it without WebGL.

Region-based: a mouth region (viseme timeline) + two eye regions (idle blink via the
blink still + subtle procedural eyebrow raises). Each region is a feathered sub-mesh
composited over the pristine static still.

    .venv-landmarks/bin/python mesh_avatar/render_anim.py [max_seconds]
writes mesh_avatar/_preview.mp4  (+ _frame_*.png samples)
"""
import json, sys, subprocess, tempfile, random
from pathlib import Path
from collections import Counter
import cv2, numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
M = json.loads((HERE / "mesh_data.json").read_text())
SIZE = M["size"]; TRI_ALL = np.array(M["triangles"], int); REF = M["ref"]
FPS = 25; TRANS_MS = 70; FEATHER = 46
MAXS = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
random.seed(7)

# timeline + audio
LIP = json.loads((REPO / "outputs/lipsync/lipsync_data.js").read_text()
                 .split("=", 1)[1].rsplit(";", 1)[0])
TL = LIP["timeline"]; AUDIO = REPO / "outputs/lipsync/audio.mp3"

RV = np.array(M["visemes"][REF]["verts"])[:, :2]
N = len(RV)

# preload images + per-viseme src(uv px) and aligned dst px
IMG, SRC, DST = {}, {}, {}
for v, d in M["visemes"].items():
    im = cv2.imread(str(REPO / "outputs/flashimage" / d["file"]))
    IMG[v] = cv2.resize(im, (SIZE, SIZE)).astype(np.float32)
    SRC[v] = np.array([[u * SIZE, (1 - w) * SIZE] for u, w in d["uv"]], np.float32)
    DST[v] = np.array([[x, y] for x, y, _ in d["verts"]], np.float32)
BG = IMG[REF].copy()

# ---- landmark groups ----
MOUTH_C = RV[[13, 14, 78, 308]].mean(0)
CHIN = RV[152]
EYE_L = RV[[33, 133, 159, 145, 160, 144]].mean(0)
EYE_R = RV[[362, 263, 386, 374, 387, 373]].mean(0)
BROW_L = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
BROW_R = [336, 296, 334, 293, 300, 285, 295, 282, 283, 276]


def region(center, R):
    """Triangles whose centroid is within R of center, + per-vertex feather alpha."""
    tris = np.array([t for t in TRI_ALL if np.hypot(*(RV[t].mean(0) - center)) < R])
    cnt = Counter()
    for a, b, c in tris:
        for i, j in ((a, b), (b, c), (c, a)): cnt[(min(i, j), max(i, j))] += 1
    boundary = {v for (i, j), n in cnt.items() if n == 1 for v in (i, j)}
    bpts = RV[list(boundary)]
    alpha = np.zeros(N, np.float32)
    used = np.unique(tris)
    for i in used:
        if i in boundary: continue
        d = float(np.sqrt(((bpts - RV[i]) ** 2).sum(1)).min())
        t = min(1.0, d / FEATHER); alpha[i] = t * t * (3 - 2 * t)
    return tris, alpha


R_MOUTH = 1.15 * float(np.hypot(*(CHIN - MOUTH_C)))
TRIS_M, ALPHA_M = region(MOUTH_C, R_MOUTH)
TRIS_EL, ALPHA_EL = region(EYE_L, 60)
TRIS_ER, ALPHA_ER = region(EYE_R, 60)
print(f"mouth tris={len(TRIS_M)}  eyeL={len(TRIS_EL)}  eyeR={len(TRIS_ER)}")


def warp_onto(bg, viseme, dst_pts, gopacity, tris, alpha):
    img = IMG[viseme]; src = SRC[viseme]; out = bg
    for tri in tris:
        s = src[tri]; d = dst_pts[tri]
        x, y, w, h = cv2.boundingRect(d.astype(np.float32))
        if w <= 0 or h <= 0: continue
        dl = d - [x, y]
        Maff = cv2.getAffineTransform(s, dl.astype(np.float32))
        patch = cv2.warpAffine(img, Maff, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        tri_mask = np.zeros((h, w), np.float32)
        cv2.fillConvexPoly(tri_mask, dl.astype(np.int32), 1.0, cv2.LINE_AA)
        av = alpha[tri]
        try:
            P = np.array([[dl[0,0], dl[0,1], 1], [dl[1,0], dl[1,1], 1], [dl[2,0], dl[2,1], 1]], np.float64)
            A, B, C = np.linalg.solve(P, av)
            yy, xx = np.mgrid[0:h, 0:w]
            amap = np.clip(A * xx + B * yy + C, 0, 1).astype(np.float32)
        except np.linalg.LinAlgError:
            amap = np.float32(av.mean())
        a3 = (tri_mask * amap * gopacity)[..., None]
        out[y:y+h, x:x+w] = patch * a3 + out[y:y+h, x:x+w] * (1 - a3)
    return out


# ---- schedules ----
smooth = lambda x: x * x * (3 - 2 * x)


def mouth_state(ms):
    """Return (src, dst, e) following the viseme timeline with TRANS_MS dissolves."""
    cur = REF
    for s in TL:
        if s["start_ms"] <= ms < s["end_ms"]:
            cur = s["viseme"] if s["viseme"] in M["visemes"] else REF
            into = ms - s["start_ms"]
            prev = REF
            idx = TL.index(s)
            if idx > 0:
                pv = TL[idx-1]["viseme"]; prev = pv if pv in M["visemes"] else REF
            if into < TRANS_MS and prev != cur:
                return prev, cur, smooth(into / TRANS_MS)
            return cur, cur, 1.0
    return REF, REF, 1.0


# blink events: random idle blinks ~ every 2.5-5s, each ~150ms close+open
BLINKS = []
t = 1.2
while t < MAXS:
    BLINKS.append(t); t += random.uniform(2.5, 5.0)
def blink_e(ms):
    s = ms / 1000.0
    for b in BLINKS:
        if b <= s < b + 0.085: return smooth((s - b) / 0.085)            # closing
        if b + 0.085 <= s < b + 0.21: return smooth(1 - (s - b - 0.085) / 0.125)  # opening
    return 0.0

# brow raise events: occasional lifts ~ every 4-7s, lift/hold/release
BROWS = []
t = 2.0
while t < MAXS:
    BROWS.append(t); t += random.uniform(4.0, 7.0)
def brow_lift(ms):
    s = ms / 1000.0
    for b in BROWS:
        if b <= s < b + 0.25: return smooth((s - b) / 0.25)             # raise
        if b + 0.25 <= s < b + 0.6: return 1.0                          # hold
        if b + 0.6 <= s < b + 0.95: return smooth(1 - (s - b - 0.6) / 0.35)  # release
    return 0.0
BROW_PX = 6.0   # max raise in px


def with_brow(verts, lift):
    """Copy verts, raise brow landmarks by lift*BROW_PX (up = -y)."""
    g = verts.copy()
    if lift > 0:
        for i in BROW_L + BROW_R: g[i, 1] -= lift * BROW_PX
    return g


dur = min(MAXS, TL[-1]["end_ms"] / 1000.0)
nframes = int(dur * FPS)
tmp = Path(tempfile.mkdtemp())
print(f"rendering {nframes} frames @ {FPS}fps ({dur:.1f}s)…")
for f in range(nframes):
    ms = f * 1000.0 / FPS
    img = BG.copy()

    # mouth
    ms_s, ms_d, me = mouth_state(ms)
    gm = DST[ms_s] + (DST[ms_d] - DST[ms_s]) * me
    img = warp_onto(img, ms_s, gm, 1.0, TRIS_M, ALPHA_M)
    if ms_d != ms_s:
        img = warp_onto(img, ms_d, gm, me, TRIS_M, ALPHA_M)

    # eyes: blink (sil->blink) + procedural brow raise, per eye region
    be = blink_e(ms); bl = brow_lift(ms)
    geom_eye = DST["sil"] + (DST["blink"] - DST["sil"]) * be
    geom_eye = with_brow(geom_eye, bl)
    for tris, alpha in ((TRIS_EL, ALPHA_EL), (TRIS_ER, ALPHA_ER)):
        img = warp_onto(img, "sil", geom_eye, 1.0, tris, alpha)        # base (brow-lifted)
        if be > 0:
            img = warp_onto(img, "blink", geom_eye, be, tris, alpha)   # blink in

    cv2.imwrite(str(tmp / f"f{f:04d}.png"), np.clip(img, 0, 255).astype(np.uint8))
    if f % 25 == 0: print(f"  {f}/{nframes}")

# sample frames: a couple generic + the first blink + the first brow raise
samples = {0, nframes//2, nframes-1}
if BLINKS: samples.add(int((BLINKS[0] + 0.085) * FPS))   # fully closed
if BROWS:  samples.add(int((BROWS[0] + 0.4) * FPS))      # brow held up
for fr in sorted(s for s in samples if 0 <= s < nframes):
    p = tmp / f"f{fr:04d}.png"
    if p.exists(): cv2.imwrite(str(HERE / f"_frame_{fr:04d}.png"), cv2.imread(str(p)))

out = HERE / "_preview.mp4"
subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
                "-t", f"{dur:.2f}", "-i", str(AUDIO),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"blinks @ {[round(b,1) for b in BLINKS]}  brows @ {[round(b,1) for b in BROWS]}")
print(f"wrote {out}")
