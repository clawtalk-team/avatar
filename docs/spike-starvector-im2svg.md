# Spike: StarVector im2svg on Gemini-Generated Face Images

**Status:** Dead end — StarVector produces malformed SVGs for photorealistic faces  
**Date:** 2026-06-04  
**Branch:** feature/runpod-avatar  

---

## Hypothesis

StarVector 1B `im2svg` model (CVPR 2025) could trace Gemini-generated face PNGs
into clean SVG vectors, giving us identity-consistent viseme frames without the
cost and latency of running Claude Opus per-viseme.

Pipeline:
1. `scripts/flashimage_generate.py` — Gemini 2.5 Flash Image via OpenRouter generates
   15 photorealistic face PNGs (one per viseme), identity-locked via base portrait reference.
2. StarVector 1B `im2svg` on GPU — traces each PNG to an SVG.
3. SVGs land in `outputs/heads/gemini_woman/` and drive the avatar widget.

---

## What We Did

### Step 1 — Gemini image generation (succeeded, already committed)

`scripts/flashimage_generate.py` generates 17 PNGs:
- 15 viseme frames (sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, I, O, U)
- 1 base portrait (reference for identity locking)
- 1 blink frame

Output: `outputs/flashimage/` — 17 PNGs, ~22 MB total. Quality: high. Identity
consistency between visemes: good. The Gemini step is validated and reusable.

### Step 2 — StarVector im2svg on Vast.ai (failed)

Spun up a Vast.ai RTX 3090 instance ($0.29/hr). Dependency hell:

| Dep | Issue |
|-----|-------|
| `svgpathtools` | Not installed by default on `nvidia/cuda` base image |
| `cairosvg` | Installed but required system `libcairo2` — missing from CUDA base |
| `open-clip-torch` | Required `meson` build tool — missing from CUDA base |
| `starvector` package | `pyproject.toml` has no `name` field → installs as `UNKNOWN 0.0.0`, not importable |

Fixes applied:
- `apt-get install -y libcairo2 libcairo2-dev meson ninja-build`
- `pip3 install svgpathtools cairosvg torchvision transformers open-clip-torch`
- Cloned star-vector repo to `/tmp/sv_src`, ran with `PYTHONPATH=/tmp/sv_src`

**Model loaded successfully.** StarVector 1B (1.43B params, 2 checkpoint shards)
loaded in ~14s on RTX 3090.

**Inference ran successfully.** 17/17 images processed, ~109s per image
(≈31 min total). Each image resized to 224×224 before inference.

### Step 3 — Inspecting the output (failed)

Downloaded all 17 SVGs. Gallery showed nothing. Investigation:

```python
import re
content = open('outputs/heads/gemini_woman/sil.svg').read()
# sil.svg: 21,040 chars
# paths: 0, rects: 2, circles: 0, fill styles: 1 (fill:none)
```

The SVG body is entirely composed of `<use xlink:href="#_Image2">` through
`<use xlink:href="#_Image122">` — 120+ references to image symbols that are
**never defined** anywhere in the file. The `<defs>` section contains only a
`<clipPath>`, not the symbol definitions. Every generated SVG has the same
structural problem.

**These SVGs render nothing.** The `<use>` elements point to `#_ImageN` IDs that
don't exist in the document.

---

## Root Cause

StarVector was trained on the SVG-Stack dataset: icons, logos, diagrams, and
typographic elements. It has essentially no training signal for photorealistic
human faces. When given a 224×224 face photo:

1. The model outputs structured boilerplate (`<use>` layout) consistent with its
   training distribution.
2. It never completes the symbol definitions — either because face images fall
   too far outside the training distribution for coherent symbol-body generation,
   or the model architecture delegates image embedding to undefined external
   symbols and the face photo produces malformed reference lists.

The output is not a truncation artifact (files are 7,000–22,000 chars, well within
the 8,000-token limit for simple icons the model was designed for). It's a
structural failure of the model on out-of-distribution input.

---

## Conclusion

**StarVector im2svg cannot vectorize photorealistic faces.** The model produces
syntactically valid but semantically empty SVGs — dangling `<use>` references
with no definitions.

This failure mode would apply to any photorealistic face input, not just these
specific images. The model is not suitable for this use case.

---

## What Works Instead

The already-validated pipeline from the prior spike:

- **Input:** `outputs/flashimage/` PNGs (Gemini 2.5 Flash Image, 15 visemes)
- **Pipeline:** MediaPipe face landmark extraction → Delaunay triangle mesh →
  per-triangle warp with smoothstep blending → canvas rendering
- **Demo:** `mesh_avatar/mesh_demo.html` (working, tested in browser)
- **Identity consistency:** Static face with only mouth region animated — no
  inter-frame drift.

See `docs/talking-head-options.md` for the full option landscape and the
`feature/runpod-avatar` commit history for the working spike code.

---

## Cost

- Gemini image generation: ~$0.30 (already done, not specific to this spike)
- Vast.ai RTX 3090: ~$0.29/hr × ~1hr = ~$0.30
- **Total spike cost: ~$0.60**

---

## Files Added This Spike

| File | Purpose |
|------|---------|
| `runpod/generate_starvector_from_images.py` | RunPod orchestrator (not used — RunPod had no capacity) |
| `scripts/flashimage_generate.py` | Gemini viseme image generator (validated) |
| `outputs/flashimage/*.png` | 17 face PNGs — gitignored (~22 MB) |
| `outputs/heads/gemini_woman/*.svg` | 17 malformed StarVector outputs — gitignored |
| `docs/spike-starvector-im2svg.md` | This document |
