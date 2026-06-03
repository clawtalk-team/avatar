# Talking-Head Animation Options — Findings & Decision

_Last updated: 2026-06-04. Author: research pass for the avatar/lipsync pipeline._

## TL;DR

| | Approach | Per-user GPU? | Looks like *the person*? | Realism | Status |
|---|---|---|---|---|---|
| ✅ **Pursue now** | **MediaPipe 2.5D mesh + blendshapes** (client-side three.js) | **No** | Yes (their own photo) | Medium — small motion only | Build prototype (separate code) |
| ✅ **Pursue now** | **Audio2Face as offline "brain"** baking ARKit-52 tracks → ship as data | **No** (offline author once) | n/a (drives the renderer above) | n/a | Fold into the prototype later |
| ⏸️ **Parked (documented)** | **MuseTalk** (2D mouth inpaint) | **Yes** | Yes | High at 256², capped | Park — per-stream GPU |
| ⏸️ **Parked (documented)** | **LivePortrait** (+ external audio driver) | **Yes** | Yes | High | Park — not natively audio-driven + per-stream GPU |
| ⏸️ **Parked (documented)** | **FantasyTalking** (Wan I2V) | **Yes** | Yes | PoC = not good enough | Park — already tried, heavy GPU |
| ⏸️ **Parked (documented)** | **Full 3D head** (MetaHuman / CC4 + A2F, Unreal render) | **Yes** (render) | ⚠️ approximate | Highest ceiling | Park — heavy infra, revisit for premium tier |
| ❌ **Dead** | **SadTalker** | Yes | — | Poor / unmaintained | Dropped |

**Product requirement note:** we do **not** need 100% photoreal of a *specific* person. A believable, near-photoreal avatar is enough. This relaxes the identity constraint across every option below (notably talkinghead and MetaHuman, where matching an exact face from one photo was the main cost/risk).

**The decisive axis is per-user GPU cost.** Anything that needs a GPU inference *per viewer / per stream* is parked regardless of quality, because it doesn't scale economically for a consumer product. The path forward is the **client-side MediaPipe 2.5D mesh** (renders in the browser, zero server GPU), optionally fed by **Audio2Face blendshape tracks baked offline once per sentence** (so the GPU cost is amortized at authoring time, not paid per user).

---

## The economic constraint (why this doc is organized the way it is)

A talking avatar for a consumer-facing product has two cost models:

1. **Per-user GPU inference** — every viewer (or every new sentence per viewer) triggers a neural forward pass on a datacenter GPU. MuseTalk, LivePortrait, FantasyTalking, and any server-side 3D render all live here. Even at "real-time" speeds, you're renting GPU-seconds per user-second. At scale this dominates COGS.
2. **Author-once, render-on-client** — the expensive computation happens once (offline, when content is created), produces a small **data artifact** (a viseme/blendshape timeline + a handful of stills or one mesh+texture), and every viewer renders it locally for free. The current 2D morph demo already lives here; so does the MediaPipe 2.5D path; so does Audio2Face *if run offline as a baker*.

**Decision: optimize for model #2.** Park model #1 options with complete docs so we can return to them for a premium/server-rendered tier later.

---

## Background: what Audio2Face actually is

NVIDIA open-sourced Audio2Face-3D on **2025-09-24** (SDK under MIT; model weights under the NVIDIA Open Model License). ([NVIDIA blog](https://developer.nvidia.com/blog/nvidia-open-sources-audio2face-animation-model/), [SDK repo](https://github.com/NVIDIA/Audio2Face-3D-SDK))

Critical fact: **A2F outputs animation signal, not pixels.** It converts audio → **ARKit-52 blendshape coefficients (≈72 incl. extras) at 30 fps** (plus an emotion track). You apply those to a *rigged face* and a renderer turns it into images. ([microservice architecture](https://docs.nvidia.com/ace/audio2face-3d-microservice/latest/text/architecture/audio2face-ms.html), [HF model card](https://huggingface.co/nvidia/Audio2Face-3D-v3.0))

- Needs an NVIDIA GPU (CUDA 12.8+, ~4 GB VRAM), runs >60 fps. Deploy as local SDK (`.so`/`.dll`), NIM microservice (gRPC), or [`nvidia-audio2face-3d` Python client](https://pypi.org/project/nvidia-audio2face-3d/).
- Does **not** animate head pose, eyes, or tongue (we handle those separately — already our design).
- `MouthClose` semantics differ from standard ARKit (includes jaw open) — a known integration gotcha.

**The key unlock for us:** A2F's 52-blendshape vocabulary is *identical* to what **MediaPipe Face Landmarker** emits. So A2F can drive a MediaPipe-derived mesh with no bespoke retargeting vocabulary. And because A2F can run **offline as a batch baker**, we get a high-quality audio→shape track *without* per-user GPU — it replaces our hand-rolled CMUdict→viseme timeline (`outputs/lipsync/lipsync_data.js`) with a trained coarticulation model, as a data file.

---

## Path A (PURSUE) — MediaPipe 2.5D mesh + blendshapes, client-side

**Idea:** the 3D evolution of the current 2D morph (`morph_demo.html`). Instead of warping pixels in the canvas plane, build a **textured face mesh** from the photo and deform it in 3D.

What MediaPipe gives us from a single photo (we already have `models/face_landmarker.task` and `scripts/extract_landmarks.py`):

1. **Fixed-topology mesh** — `canonical_face_model.obj` (468 verts, fixed topology, UVs). Fit it to the 478 detected landmarks, project the photo as texture.
2. **52 ARKit blendshapes** — the Face Landmarker blendshape model emits the ARKit-52 set (same as A2F). _(Our current extractor doesn't enable this output yet — the prototype will.)_
3. **Facial transformation matrix** — head pose, so pose and expression stay decoupled (matches our "handle blink/head-move separately" decision).

Pipeline: `photo → MediaPipe mesh + texture + blendshape rig → drive blendshapes (from our viseme timeline now, A2F later) → render in three.js, in the browser`. **Zero per-user GPU.**

### Honest caveats (this is the "what you read isn't what you get" part)
- ❌ **It's a face, not a head** — frontal shell only; no scalp, back of head, ears, neck, hair. Composite back onto the original still.
- ❌ **Depth is weak** — MediaPipe Z is estimated relative depth, not a metric scan. Head-on is fine; **profile / large rotation breaks it.** Acceptable for the small-motion talking head we've already validated.
- ❌ **Single-photo texture = occlusion** — sides, **teeth, mouth interior** aren't captured. The open-mouth interior is the exact difficulty we hit with 2D morph; 2.5D doesn't solve it — we still synthesize/fake the inner mouth.
- ❌ Under scrutiny it's a **textured puppet**, not a 3D human. Good for subtle speech; not MetaHuman-grade.

### Why pursue it anyway
- ✅ **No per-user GPU** — renders on the client like the current demo.
- ✅ Builds directly on assets we already have (stills, landmarks, timeline).
- ✅ Gives a **real blendshape rig** — so Audio2Face (or MediaPipe's own blendshapes) can drive it later with no custom retarget layer.
- ✅ Adds a genuine 3D substrate (subtle head turn, parallax) over flat 2D warp, improving the "alive" feeling without leaving the browser.

> Build as **separate code** from the working 2D morph pipeline so the current demo stays unbroken (it may be good enough for an initial demo).

---

## Path B (PURSUE) — Audio2Face as an offline shape baker

Run A2F **once, offline**, on our Deepgram audio to produce an ARKit-52 blendshape track per sentence; ship that JSON as the timeline. The client renderer (Path A) consumes it. GPU cost is paid once at authoring, never per user.

- ✅ Fixes the "timeline-driven, not audio-driven" weakness with a trained model.
- ✅ Output plugs straight into the MediaPipe mesh rig (shared blendshape vocabulary).
- ⚠️ Requires a one-time CUDA GPU at content-authoring time (not per user). Easy to run as a batch job / on a rented GPU during content production.
- ⚠️ `MouthClose` jaw-open quirk needs a small mapping fix.

This is sequenced *after* the Path A prototype proves the rig; initially the prototype is driven by our existing viseme timeline.

---

## Parked options (complete docs — revisit for a premium/server-rendered tier)

> All of these need a GPU **per inference/stream**, i.e. per-user GPU cost. Parked on economics, not capability.

### MuseTalk (TMElyralab) — 2D mouth-region inpainting
- Edits the mouth region of an existing **video/frame** in latent space. Conceptually closest to our mouth-mask morph, but neural. ([repo](https://github.com/TMElyralab/MuseTalk), [arXiv](https://arxiv.org/html/2410.10122v3))
- **Real numbers:** 30 fps+ at **256×256 face region** on a Tesla V100. That 256² is a **hard quality ceiling**. On a 4 GB laptop GPU (RTX 3050 Ti), an 8-second clip took **~5 minutes** — "real-time" needs a real datacenter GPU.
- **Known limitations (from the repo):** loses fine detail (mustache, lip shape/color); single-frame pipeline → **jitter**; teeth softer than commercial tools despite the two-stage GAN+sync training.
- **Verdict:** the strongest open 2D option and the closest to our morph mental model, but the 256² cap + per-stream GPU make it a parked premium option. **Worth a real test if/when we accept server GPU.**

### LivePortrait (Kuaishou) — portrait animator, **not natively audio-driven**
- High-fidelity expression/pose transfer from a **driving video**, on a single image. It is a **renderer/animator, not an audio→mouth solution**. To lipsync to our fixed audio you bolt on a separate driver (e.g. LipSick, or feed it A2F output). ([issue #156](https://github.com/KwaiVGI/LivePortrait/issues/156), [issue #310](https://github.com/KwaiVGI/LivePortrait/issues/310))
- **Real-world notes:** fp16 causes face flicker (use fp32); reported lip motion under-pronounced for pure lipsync; needs a recent GPU for interactive speeds.
- **Verdict:** excellent for adding head/eye/expression life, but it does not by itself solve audio-driven mouth, and it's per-stream GPU. Parked; potentially useful *combined* with another mouth driver later.

### FantasyTalking (Wan 2.2 I2V + Wav2Vec) — already tried
- Audio-driven talking portrait via Wan, 480×832 @ 23 fps, 2-pass (30 steps). ~5–8 min per clip on an RTX 6000. ([approach #6 in README])
- **Our PoC verdict: not good enough.** Heavy GPU per clip, slow, quality didn't justify it. Parked.

### Full 3D head (MetaHuman / Reallusion CC4 + Audio2Face)
The "intended" A2F path: rig a photoreal 3D head, drive with A2F, render in Unreal/Omniverse.

Acquisition paths from a single photo (skeptical real-world read):
- **Epic MetaHuman + Mesh-to-MetaHuman:** strongest realism ceiling and native A2F/LiveLink support. From *one* photo you typically go photo → mesh via **KeenTools FaceBuilder** (or photogrammetry) → wrap onto MetaHuman topology. Result resembles the subject but is usually **"close-ish," not an exact match**, and tuning to a specific face is real work. ([photo→MetaHuman guide](https://yelzkizi.org/metahuman-from-a-photo/), [MetaHuman + A2F](https://yelzkizi.org/metahuman-and-nvidia-omniverse-audio2face/))
- **Reallusion Character Creator 4 + Headshot 2:** single-photo → head, with iClone↔Audio2Face integration. Faster than MetaHuman, slightly lower ceiling; commercial license needed.
- **A2F outputs ~72 blendshapes incl. ARKit-52** to drive MetaHuman in UE5 with lip-sync + expressions.
- **Economics:** rendering is **server-side GPU per user** (or pre-rendered video). Heaviest infra of all options.
- **Verdict:** highest quality ceiling, best for a premium tier or pre-rendered hero content. Parked until per-user-GPU economics are acceptable or output is pre-baked to video.

### met4citizen/talkinghead — TODO: explore (client-side full-3D-head)
[github.com/met4citizen/talkinghead](https://github.com/met4citizen/talkinghead) — a browser-native 3D talking-head library that may be the cleanest **client-side full-head** path (no per-user GPU). Strong fit signals:
- **MIT**, three.js/WebGL, runs entirely client-side — same zero-per-user-GPU economics as our chosen path.
- Drives the **exact 15 Oculus visemes we already generate** (`sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, I, O, U`) **plus the ARKit-52 set** — i.e. the Audio2Face vocabulary. So both our current timeline *and* A2F output drive it with no retargeting.
- `speakAudio({audio, words, wtimes, wdurations})` takes audio + word-level timing directly — we already produce that (Deepgram audio + Whisper word timestamps). It also accepts pre-computed visemes/blendshapes, so an A2F bake drops straight in.
- Uses **GLB heads** (Ready Player Me / Avaturn ≈ near-photoreal; VRoid = anime). Mixamo-rigged, so it also gets head/eye/gesture motion for free — the thing our single-photo 2.5D mesh *can't* do.

Note (per product decision): **we do NOT need 100% photoreal of a specific person.** A believable, near-photoreal avatar (RPM/Avaturn) is acceptable — so the "close-ish, not exact-identity from one photo" caveat is **not a blocker** for this option (or for MetaHuman). That removes the main downside and makes talkinghead a front-runner: real rigged head + free head/eye/gesture motion, client-side, no per-user GPU. **Spike:** load an RPM/Avaturn GLB, feed our existing audio + word timing via `speakAudio()`, and judge realism + effort against (a) the MediaPipe 2.5D mouth-mesh prototype and (b) the parked MetaHuman path. It sits between them: more "alive" than the 2.5D mesh, lighter than MetaHuman.

### SadTalker — DEAD
Single-image + audio talking head with head motion. **Effectively unmaintained / poor quality in 2026 — dropped.** Listed only so we don't re-evaluate it.

---

## Recommendation & sequencing

1. **Now:** build the **MediaPipe 2.5D mesh prototype** as separate code (Path A), driven by the existing viseme timeline. Keep `morph_demo.html` untouched as the fallback demo.
2. **Next:** if 2.5D adds enough life, wire **Audio2Face offline baking** (Path B) to replace the CMUdict timeline with trained blendshape tracks — still zero per-user GPU.
3. **Later / premium tier:** revisit **MuseTalk** (accept server GPU for higher fidelity) and the **full 3D MetaHuman + A2F** path for pre-rendered hero content. Both fully documented above so we can pick up without re-researching.

---

## Sources
- [NVIDIA open-sources Audio2Face (blog)](https://developer.nvidia.com/blog/nvidia-open-sources-audio2face-animation-model/)
- [Audio2Face-3D SDK (GitHub, MIT)](https://github.com/NVIDIA/Audio2Face-3D-SDK)
- [Audio2Face-3D microservice architecture](https://docs.nvidia.com/ace/audio2face-3d-microservice/latest/text/architecture/audio2face-ms.html)
- [Audio2Face-3D model card (Hugging Face)](https://huggingface.co/nvidia/Audio2Face-3D-v3.0)
- [MuseTalk (GitHub)](https://github.com/TMElyralab/MuseTalk) · [MuseTalk paper](https://arxiv.org/html/2410.10122v3)
- [LivePortrait audio/lipsync issue #156](https://github.com/KwaiVGI/LivePortrait/issues/156) · [#310](https://github.com/KwaiVGI/LivePortrait/issues/310)
- [Photo → MetaHuman guide](https://yelzkizi.org/metahuman-from-a-photo/) · [MetaHuman + Audio2Face](https://yelzkizi.org/metahuman-and-nvidia-omniverse-audio2face/)
- [Open-source lip-sync roundup (2026)](https://lipsync.com/blog/open-source-lip-sync) · [Pixazo list](https://www.pixazo.ai/blog/best-open-source-lip-sync-models)
