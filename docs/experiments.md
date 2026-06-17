# Experiments & Research History

This document captures the approaches tried during development of the Voxhelm avatar
toolkit, including what worked, what didn't, and why.

---

## 1. Stable Diffusion inpainting (abandoned)

**Idea:** Generate a base portrait with SD, then inpaint just the mouth region with a
different prompt per viseme. ControlNet + fixed seed were meant to lock identity so only
the mouth changed.

**Implementation:** `generator.py` — SD pipeline with inpainting mask around the mouth,
driven by viseme-specific prompts.

**Why it failed:** SD inpainting at the scale of a mouth region is too unstable. Even with
ControlNet and a fixed seed, the face drifts frame-to-frame — different lighting, slightly
different face shape, eyes in different positions. The result is obvious flickering when you
play frames in sequence. Consistent identity across 15 viseme frames proved unachievable
without per-frame manual curation.

---

## 2. Parametric SVG cartoon (working demo, superseded)

**Idea:** Abandon AI image generation entirely. Define mouth geometry as a function of
three float parameters and compute SVG bezier curves analytically.

```
(jaw_open, lip_spread, lip_part)
  jaw_open   0.0 = closed  →  1.0 = fully open jaw drop
  lip_spread -1.0 = pursed  →  0.0 = neutral  →  1.0 = wide smile
  lip_part   negative = pressed  →  0.0 = touching  →  1.0 = max open
```

Each of the 15 OVR LipSync visemes maps to a `(jaw, spread, part)` triple:

| Viseme | jaw  | spread | part | Phonemes |
|--------|------|--------|------|----------|
| sil    | 0.00 | +0.00  | 0.00 | silence |
| PP     | 0.00 | +0.00  | -0.20 | p, b, m |
| FF     | 0.05 | +0.15  | +0.20 | f, v |
| TH     | 0.10 | +0.00  | +0.30 | th, dh |
| DD     | 0.15 | +0.10  | +0.30 | t, d |
| kk     | 0.20 | +0.00  | +0.25 | k, g |
| CH     | 0.12 | -0.35  | +0.28 | ch, j, sh |
| SS     | 0.05 | +0.50  | +0.12 | s, z |
| nn     | 0.10 | +0.05  | +0.20 | n, l, ng |
| RR     | 0.15 | -0.28  | +0.25 | r |
| aa     | 0.85 | +0.15  | +0.80 | ah, aa |
| E      | 0.40 | +0.30  | +0.50 | eh, ey |
| I      | 0.05 | +0.55  | +0.10 | ih, iy |
| O      | 0.45 | -0.40  | +0.52 | oh, ao |
| U      | 0.18 | -0.65  | +0.28 | oo, uw |

`svg_generator.py` computes bezier control points from these parameters and produces
complete face SVGs (512x512). Identity across frames is 100% guaranteed because everything
outside the mouth is static.

Superseded by Claude SVG generation which produces more expressive, customisable characters.

---

## 3. Deepgram TTS + Whisper + CMUdict lipsync pipeline

**Pipeline** (`scripts/lipsync_pipeline.py`):

1. **Deepgram TTS** — `POST /v1/speak` with `model=aura-asteria-en`, returns MP3.
2. **Whisper word timestamps** — `whisper.transcribe(audio, word_timestamps=True)` with
   the `base` model. Returns per-word `{word, start, end}` in seconds.
3. **CMUdict phoneme lookup** — `nltk.corpus.cmudict` maps each word to its ARPAbet
   phoneme sequence (e.g. HELLO → [HH, AH, L, OW]).
4. **ARPAbet → viseme mapping** — 40+ ARPAbet phones map to the 15 OVR visemes.
5. **Timeline builder** — phonemes distributed uniformly across each word's time span.

This pipeline is now integrated into the voxhelm package (`voxhelm.core.audio` and
`voxhelm.core.timeline`).

---

## 4. Smooth viseme transitions

Hard-cutting between viseme frames looks mechanical. The three float parameters are lerped
at 60fps with smoothstep easing (`t²(3−2t)`) over a 55ms transition window. Because
`prevShape` is snapshotted at the *current interpolated position*, transitions chain
smoothly even when a new viseme arrives before the previous transition completes.

---

## 5. Flutter macOS native app

Port of the parametric SVG approach to a Flutter `CustomPainter`. Uses the same 512x512
coordinate system and bezier geometry. Lives in `avatar_demo/`.

---

## 6. RunPod / ComfyUI — Wan 2.2 AI video generation

**Idea:** Replace the SVG cartoon with a real AI-generated photorealistic portrait,
using neural audio conditioning for lip sync.

Lives in `runpod/`. All scripts talk to a ComfyUI instance on a RunPod pod (RTX PRO 6000
Blackwell, 96GB VRAM) via its REST API.

### Wan 2.2 MoE architecture
- **High-noise expert** — handles steps 0–20 (layout, structure, identity)
- **Low-noise expert** — handles steps 20–30 (refinement, detail)

### Scripts
- `generate_sample.py` — T2V smoke test
- `generate_viseme.py` — T2V viseme sequence (single pass)
- `generate_viseme_i2v.py` — 4-phase I2V pipeline (consistent avatar)
- `generate_fantasy_talking.py` — Audio-driven lip sync via FantasyTalking + Wav2Vec
- `pod.py` — Pod lifecycle management

---

## 7. Flash Image visemes + MediaPipe morph (working, integrated into voxhelm)

**Idea:** Generate photoreal stills per viseme with Gemini Flash Image, then morph between
them with landmark-driven warping.

Now integrated into the voxhelm package as `--mode photo`. See the main README for usage.

Key lessons learned:
- Identity lock: edit one base portrait rather than generating 15 independently
- Similarity alignment must use only rigid landmarks (eyes/nose/forehead) — including
  the chin made open-mouth frames rescale the whole head
- Viseme prompts need explicit "relaxed eyebrows, neutral eyes" instruction

---

## 8. StarVector im2svg (dead end)

Attempted to use StarVector ML model to convert photorealistic PNGs to SVGs. The model
was trained on vector primitives (icons, diagrams) and doesn't produce complex character
faces well. SVG path topology differs frame-to-frame, blocking smooth interpolation.

See `docs/spike-starvector-im2svg.md` for the detailed writeup.

---

## Implementation candidates comparison

Both working pipelines share the same audio pipeline and animation architecture.

| Dimension | SVG cartoon | Photo (Flash Image) |
|-----------|-------------|---------------------|
| Visual fidelity | Cartoon / flat design | Photorealistic |
| Rendering | Widget/DOM swap | Per-triangle affine warp |
| Asset size (per char) | ~50 KB (15 SVGs) | ~1–2 MB (15 PNGs + geometry) |
| Transition smoothness | Hard frame-switch | Smooth morph + cross-dissolve |
| Generation cost | ~$0.10–0.50 | ~$0.60 |
| Character variety | 6 presets + custom | Custom via style description |
| Runtime GPU | None | None |
