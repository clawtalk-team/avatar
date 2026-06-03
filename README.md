# Photo Generation / Avatar Lipsync

Research and implementation work toward a real-time talking avatar — a photorealistic
or stylised face that animates in sync with speech audio. This repo documents each
approach attempted, what worked, what didn't, and what's next.

---

## Approaches tried

### 1. Stable Diffusion inpainting (abandoned)

**Idea:** Generate a base portrait with SD, then inpaint just the mouth region with a
different prompt per viseme. ControlNet + fixed seed were meant to lock identity so only
the mouth changed.

**Implementation:** `generator.py` — SD pipeline with inpainting mask around the mouth,
driven by viseme-specific prompts. `scripts/base_face.png` is the reference portrait.

**Why it failed:** SD inpainting at the scale of a mouth region is too unstable. Even with
ControlNet and a fixed seed, the face drifts frame-to-frame — different lighting, slightly
different face shape, eyes in different positions. The result is obvious flickering when you
play frames in sequence. Consistent identity across 15 viseme frames proved unachievable
without per-frame manual curation.

---

### 2. Parametric SVG cartoon (working demo)

**Idea:** Abandon AI image generation entirely for now. Instead, define mouth geometry as
a function of three float parameters and compute SVG bezier curves analytically.

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
complete face SVGs (512×512, all in-process, no dependencies beyond stdlib). The full
face includes: background, neck, ears, hair (clipped ellipse + sideburns with texture),
head oval (radial gradient), eyebrows (quadratic bezier), eyes (whites/iris/pupil/
highlight), nose, cheek blush, and the mouth layer (cavity, teeth, tongue, upper lip,
lower lip, highlight).

**Browser demo:** `demo.html` — single inline SVG with `<g id="mouth-group">`. Only that
group's innerHTML is replaced per frame (DOM-swap), which avoids SVG reload flicker.
Geometry functions are ported directly to JS so the browser recomputes bezier paths
from float parameters rather than swapping pre-baked SVG strings.

**Key technical detail:** identity across frames is 100% guaranteed because everything
outside the mouth is static — the face itself doesn't move, only the mouth geometry
recomputes.

---

### 3. Real lipsync — Deepgram TTS + Whisper + CMUdict

**Idea:** Drive the SVG mouth animation from real speech audio with accurate timing.

**Pipeline** (`scripts/lipsync_pipeline.py`):

1. **Deepgram TTS** — `POST /v1/speak` with `model=aura-asteria-en`, returns MP3.
   API key in `.env` as `DEEPGRAM_API_KEY`.
2. **Whisper word timestamps** — `whisper.transcribe(audio, word_timestamps=True)` with
   the `base` model. Returns per-word `{word, start, end}` in seconds.
3. **CMUdict phoneme lookup** — `nltk.corpus.cmudict` maps each word to its ARPAbet
   phoneme sequence (e.g. HELLO → [HH, AH, L, OW]). Stress digits stripped.
4. **ARPAbet → viseme mapping** — 40+ ARPAbet phones map to the 15 OVR visemes
   (e.g. AH→aa, OW→O, L→nn). Unknowns and gaps → sil.
5. **Timeline builder** — phonemes are distributed uniformly across each word's time
   span. Gaps between words and leading/trailing silence → sil frames.
6. **Output** — `outputs/lipsync/audio.mp3` + `outputs/lipsync/lipsync_data.js`, which
   sets `window.LIPSYNC_DATA = {sentence, audio, timeline}`. Loaded via `<script src>`
   (avoids CORS issues on `file://`).

`demo.html` plays the audio element and drives the render loop from
`audio.currentTime * 1000` — perfectly synced to actual playback without manual
time accumulation. Playback rate (speed) is controllable.

---

### 4. Smooth viseme transitions

**Idea:** Hard-cutting between viseme frames looks mechanical. Real speech has continuous
muscle movement between mouth positions.

**Implementation:** Rather than pre-baking transition frames (which would require 15×15=225
pairs), the three float parameters `(jaw, spread, part)` are lerped at 60fps with smoothstep
easing (`t²(3−2t)`) over a 55ms transition window.

```js
// On each viseme change:
prevShape = current interpolated position  // snapshot mid-transition
targShape = new viseme shape
transStart = now

// Each RAF frame:
t = clamp((now - transStart) / TRANSITION_MS, 0, 1)
t = t * t * (3 - 2 * t)   // smoothstep
interpShape = lerp(prevShape, targShape, t)
// recompute mouth beziers from interpShape
```

Because `prevShape` is snapshotted at the *current interpolated position*, transitions
chain smoothly even when a new viseme arrives before the previous transition completes.

---

### 5. Flutter macOS native app

**Idea:** Run the same avatar demo natively on macOS as a Flutter app.

**Implementation** (`avatar_demo/lib/main.dart`):

- `AvatarPainter extends CustomPainter` — draws the full face on a `Canvas` using the
  exact same coordinate system (512×512 logical units) and geometry constants as the
  Python/JS implementations. Mouth uses `Path..cubicTo()` for the same bezier curves.
- `Ticker` fires at 60fps; `onPositionChanged` from `audioplayers` updates `_audioPos`.
  Each tick: look up current viseme by timestamp, detect changes, snapshot `_prevShape`,
  smoothstep-lerp to `_targShape`, call `setState`.
- `AudioPlayer` plays `assets/audio/audio.mp3`; lipsync data is bundled as
  `assets/data/lipsync_data.json`.
- macOS sandbox requires `com.apple.security.network.client` in both
  `DebugProfile.entitlements` and `Release.entitlements` for audioplayers to work
  even with local assets.

---

### 6. RunPod / ComfyUI — Wan 2.2 AI video generation

**Idea:** Replace the SVG cartoon face with a real AI-generated photorealistic portrait,
and drive lip sync with neural audio conditioning rather than rule-based viseme mapping.

The work lives in `runpod/`. All scripts talk to a ComfyUI instance running on a RunPod
pod (RTX PRO 6000 Blackwell, 96GB VRAM) via its REST API (`/prompt`, `/history/{id}`,
`/view`). Authentication is RunPod's Bearer token proxy.

#### Model: Wan 2.2 MoE

Wan 2.2 uses a Mixture-of-Experts architecture with two separate UNet checkpoints:
- **High-noise expert** (`wan2.2_*_high_noise_14B_fp16.safetensors`) — handles steps
  0–20, responsible for layout, structure, and identity.
- **Low-noise expert** (`wan2.2_*_low_noise_14B_fp16.safetensors`) — handles steps
  20–30, responsible for refinement and fine detail.

Both T2V (text-to-video) and I2V (image-to-video) variants exist. The two-pass
sampling runs as a single ComfyUI workflow with `start_step`/`end_step` on each
`WanVideoSampler` node.

#### Smoke test: `generate_sample.py`

T2V generation of a presenter video. 81 frames at 24fps = 3.375s. Confirms the
ComfyUI API is reachable and the pipeline works end-to-end before running heavier jobs.

#### Portrait generation: `generate_viseme.py`

Single-pass T2V, portrait orientation (480×832), 81 frames. Prompt describes the
SIL→PP→FF viseme sequence in natural language. Output is a short clip showing the
transition. **Less character-consistent** than the I2V approach because there's no
pixel-level anchor frame — the model interprets the prompt but has no identity lock.

#### I2V anchor pipeline: `generate_viseme_i2v.py`

Four-phase pipeline that enforces character consistency across all viseme frames:

```
Phase 1 — T2V:  prompt = CHARACTER + SIL mouth description
                → generate 5 frames, extract frame 0 as the "identity anchor"

Phase 2 — I2V:  start_image = SIL frame 0,  prompt = CHARACTER + PP mouth description
                → 25 frames; last frame IS the PP still; video is SIL→PP clip

Phase 3 — I2V:  start_image = PP last frame, prompt = CHARACTER + FF mouth description
                → 25 frames; last frame IS the FF still; video is PP→FF clip

Phase 4 — I2V:  start_image = FF last frame, prompt = CHARACTER + SIL description
                → 25 frames; video is FF→SIL loop-back clip
```

`noise_aug_strength=0.0` on `WanVideoImageToVideoEncode` locks the start frame's pixel
identity — everything outside the mouth stays consistent across all clips because each
phase is anchored to the previous one's final frame. The SIL base portrait (Phase 1,
frame 0) becomes the input for FantasyTalking.

#### Audio-driven lip sync: `generate_fantasy_talking.py`

FantasyTalking is a ComfyUI custom node that patches the Wan 2.2 I2V model with audio
conditioning via Wav2Vec embeddings. Instead of text-described mouth shapes, the model
reads the audio waveform directly and generates matching mouth motion.

```
audio.wav → Wav2Vec (facebook/wav2vec2-base-960h) → FantasyTalkingWav2VecEmbeds
portrait.png → WanVideoImageToVideoEncode (noise_aug=0.0)
                     ↓
               WanVideoSampler (high-noise, steps 0-20) ← fantasytalking_embeds
                     ↓
               WanVideoSampler (low-noise, steps 20-30) ← fantasytalking_embeds
                     ↓
               WanVideoDecode → VHS_VideoCombine (mp4 with audio muxed in)
```

Input audio can be any WAV file — the script defaults to macOS TTS (`say` + `afconvert`)
as a fallback. Number of video frames is derived from audio duration × FPS (23.0).

#### Pod management: `pod.py`

Thin wrapper around the RunPod GraphQL API for pod lifecycle. Reads `RUNPOD_API_KEY`
and `RUNPOD_POD_ID` from `.env` at the project root. Commands: `status`, `start`,
`stop`, `url`. Stop the pod when not generating — billing is per-hour.

---

### 7. Flash Image visemes + MediaPipe morph (working spike, superseded by #8)

**Idea:** The photorealistic version of approach #2. Instead of hand-coded bezier
geometry, generate a photoreal still per viseme with an identity-locked image model,
then morph between stills with landmark-driven warping — keeping the exact same
timeline-driven animation architecture (static face, only the mouth moves, smoothstep
blend on each viseme change). This is the GPU-free, real-time path: no Veo video (which
generates its own audio and can't be driven by our timeline), no RunPod pod.

**Pipeline:**

1. **Stills — `scripts/flashimage_generate.py`.** Gemini 2.5 Flash Image (nano-banana)
   via OpenRouter (`OPENROUTER_API_KEY` in `.env`, ~$0.04/image). Generate ONE base
   portrait (text-to-image), then for each of the 15 OVR visemes, *edit only the mouth*
   of that base ("same person, identical everything, change only the mouth to …"). Editing
   one base — rather than generating 15 faces independently — is what keeps identity stable;
   it's the lesson from the failed SD-inpainting run (#1). Output: `outputs/flashimage/<viseme>.png`
   + `manifest.json`.

2. **Landmarks — `scripts/extract_landmarks.py`.** MediaPipe FaceLandmarker (478 points)
   on each still. nano-banana drifts head scale slightly between generations, so each still
   is **similarity-aligned to `sil`** using stable points (eyes/nose/contour) — only the
   mouth then differs frame-to-frame. Fixed border anchors pin the perimeter, and one shared
   Delaunay triangulation (970 triangles over 498 points) is computed from the reference
   frame. All of this is precomputed offline into `outputs/flashimage/geometry.json` so the
   browser needs no MediaPipe, WebGL, or CDN at runtime. (MediaPipe needs Python ≤3.12, so
   this runs in a separate `.venv-landmarks`; the rest of the repo is fine on 3.14.)

3. **Morph demo — `morph_demo.html`.** Pure canvas-2D. Loads the stills + `geometry.json` +
   the existing Deepgram/Whisper timeline (`outputs/lipsync/lipsync_data.js`) and audio. The
   render loop is the same as `demo.html`: look up the current viseme by `audio.currentTime`,
   snapshot on change, smoothstep-blend over a ~42ms (24fps) window. **Mouth-region
   compositing:** every frame draws ONE static `sil` face as the base (so the head never
   jitters), then composites only a feathered elliptical mouth patch on top — the morphed
   mouth (per-triangle affine warp + cross-dissolve of prev→cur viseme) clipped to the mask
   via `destination-in`. The mask extent is the bounding box of the mouth/jaw landmarks across
   all visemes, so an open jaw still fits. Missing visemes fall back to the nearest generated
   mouth shape, so the demo runs end-to-end at any coverage level. **Idle blink:** a
   second eyes-closed still (`blink.png`) is composited the same way through a feathered
   eye-region mask, driven by a wall-clock timer (~10s ± randomness, occasional double-blink)
   so the avatar blinks even when paused/idle — independent of the audio timeline.

**Result:** All 15 visemes generate with consistent identity; the open-mouth interior
(teeth/tongue) that pure morphing can't invent comes from the target still via the
cross-dissolve. Because everything outside the feathered mouth mask is a single static
image, the head is rock-steady — no inter-frame jitter. Verified end-to-end in a headless
browser — `audio.currentTime` drives the viseme badge and the canvas morph through an
11.8s, 4-sentence passage exercising all 15 visemes, no JS errors.

Two alignment lessons baked in: (1) the similarity alignment must use only rigid landmarks
(eyes/nose/forehead) — including the chin made open-mouth frames rescale the whole head;
(2) viseme prompts need an explicit "relaxed eyebrows, neutral eyes" instruction or the
model adds a surprised expression on wide vowels.

**Why this beats the alternatives for a real-time photoreal avatar:** ~$0.60 one-time
generation vs ~$96/sentence for per-viseme Veo video; runs client-side with no GPU vs the
RunPod/FantasyTalking stack; reuses the existing timeline that Veo can't consume.

---

### 8. Claude-generated SVG visemes + Deepgram audio demo (current)

**Idea:** Use Claude Opus 4.6 to generate cartoon face SVGs per viseme via prompt. Unlike
the parametric approach (#2) the art quality is AI-generated and expressive; unlike the
Flash Image approach (#7) there is no pixel warping or landmark extraction — each frame is
a standalone SVG and switching between them is an instant DOM swap. This became the
foundation for a full head studio.

**Why SVG over pixel stills:** SVG keeps everything outside the mouth static (no inter-frame
jitter), scales to any resolution, is trivially bundleable in a Flutter app as asset strings,
and needs zero GPU at runtime.

#### 8a — Single head generation

`scripts/generate_head.py` generates a complete set of 15 viseme SVGs for one character.
The `sil` (closed mouth) frame is generated first and embedded in every subsequent prompt
as a pixel-level reference, which is what locks character identity across all 15 frames.

```
python scripts/generate_head.py --preset young_woman
python scripts/generate_head.py --style "elderly man, white hair, kind expression, flat design"
python scripts/generate_head.py --list-presets   # show all 6 bundled characters
```

Outputs to `outputs/heads/<name>/` — 15 SVGs + `gallery.html`.

#### 8b — Batch generation (6 presets)

`scripts/generate_heads_batch.py` generates all 6 bundled preset characters (young/middle/older
× male/female) in one run and builds a combined `showcase.html`. `--skip-existing` resumes
an interrupted run without re-generating SVGs that already exist.

```
python scripts/generate_heads_batch.py --skip-existing
```

6 bundled presets:

| Key | Description |
|-----|-------------|
| `young_man` | young man, mid-20s, short dark hair, light skin, clean-shaven |
| `middle_man` | middle-aged man, 40s, salt-and-pepper stubble, medium-brown skin |
| `older_man` | elderly man, 70s, white hair, weathered warm skin, kind eyes |
| `young_woman` | young woman, mid-20s, long auburn hair, fair freckled skin |
| `middle_woman` | middle-aged woman, 40s, dark hair with grey streaks, medium-brown skin |
| `older_woman` | elderly woman, 70s, silver bun, light wrinkled skin, rosy cheeks |

#### 8c — Audio-driven demo

`scripts/viseme_demo.py` generates a self-contained `outputs/viseme_demo.html` with:

- **Deepgram TTS** (`aura-2-thalia-en`) for speech synthesis
- **Deepgram STT** (`nova-3` with `timestamps=true`) for word-level timing
- **CMUdict** phoneme lookup + ARPAbet → viseme mapping within each word's time window
- Speed controls (0.25×, 0.5×, 1×)
- Idle eye-blink overlay (two SVG ellipses animating `ry` 0→28→0, 4–9s intervals)
- Three sample sentences covering all 15 visemes

TTS/STT results are cached in `outputs/viseme_cache/` so subsequent runs are instant.

#### 8d — Web studio

`webapp/server.py` is a FastAPI server (default port 7432) that wraps the generation
and audio APIs into a browser UI. `webapp/index.html` is a single-page app with:
- **Sidebar:** preset picker, custom style input, head list with thumbnails
- **Gallery tab:** all 15 viseme frames for the selected head
- **Demo tab:** full audio-driven lip-sync with custom sentence input and speed controls

```
python webapp/server.py
open http://localhost:7432
```

**Key technical detail:** `safe_json()` replaces `</` with `<\/` in SVG content embedded
inside `<script>` blocks — SVG paths containing `</path>` would otherwise break the
HTML parser and silently kill all JavaScript.

---

## Current state

| Component | Status |
|-----------|--------|
| SVG parametric cartoon | Working — `demo.html` |
| Deepgram TTS | Working — `outputs/lipsync/audio.mp3` |
| Whisper word timestamps | Working |
| CMUdict viseme mapping | Working |
| Smoothstep transitions | Working |
| Browser lipsync demo | Working — open `demo.html` |
| Flash Image visemes (15) | Working — `outputs/flashimage/` |
| MediaPipe morph demo | Working — open `morph_demo.html` |
| Flutter macOS app | Working — `avatar_demo/` |
| **Claude SVG viseme generation** | **Working — `scripts/generate_head.py`** |
| **6-preset batch generation** | **Working — `scripts/generate_heads_batch.py`** |
| **Audio-driven SVG demo** | **Working — `outputs/viseme_demo.html`** |
| **Head studio web app** | **Working — `webapp/server.py`** |
| **Flutter integration guide** | **Written — `docs/flutter_integration.md`** |
| RunPod infrastructure | Implemented, not yet run on live pod |
| Wan 2.2 T2V avatar | Not yet generated |
| Wan 2.2 I2V viseme pipeline | Not yet generated |
| FantasyTalking lipsync | Not yet generated |

---

## Planned

### Near term

**Flutter integration:** Wire the SVG avatar into the ClaWTalk Flutter app (Voxhelm).
See `docs/flutter_integration.md` for the full plan. Key steps:
- Add `clawtalk_avatar` Flutter package (`flutter_svg` + `VisemeController` + `BlinkController`)
- Add ElevenLabs TTS client to voice-gateway with character-level alignment output
- Add `phoneme_timeline` WebSocket message type carrying `{t, viseme}` events to Flutter
- Mount `ClaWTalkAvatar` widget in `CallScreen` alongside existing `AgentAudioVisualizer`
- ~4.5 days for production-ready integration; ~2 days for a bundled demo

**End-to-end photorealistic avatar pipeline (RunPod):**
1. Start the RunPod pod
2. Run `generate_viseme_i2v.py` to produce the photorealistic SIL portrait
3. Feed `outputs/lipsync/audio.mp3` into `generate_fantasy_talking.py` with the SIL portrait
4. The result is a photorealistic talking head video synced to the TTS audio

### Longer term

**Real-time inference:** FantasyTalking and the full Wan 2.2 pipeline are batch-oriented
(minutes per clip on an RTX 6000). For a real-time talking avatar, the options are:
- **Pre-generate per sentence** — generate a video for each likely TTS utterance and cache it.
- **Faster models** — SadTalker, Hallo, etc. trade quality for speed; some near-real-time.
- **Hybrid** — keep the SVG mouth for real-time response but composite over an AI portrait.

**Expand character library:** The 6 presets cover basic demographics. Add more styles
(fantasy characters, robots, animals, brand mascots) using `generate_head.py --style`.

**StarVector (exploratory):** A neural model that generates SVG natively from text/image.
Could produce more organic mouth shapes than the current analytic geometry while keeping
the SVG DOM-swap architecture. Main uncertainty: SVG paths need matching topology between
visemes to allow control-point interpolation.

---

## Project structure

```
demo.html                   Browser lipsync demo (SVG cartoon + Deepgram audio)
morph_demo.html             Browser lipsync demo (Flash Image stills + MediaPipe morph)
svg_generator.py            Parametric SVG face generator (15 visemes)
generator.py                Original SD inpainting approach (abandoned)

scripts/
  generate_head.py          Generate 15-viseme SVG set for one character (CLI)
  generate_heads_batch.py   Batch-generate all 6 preset characters + showcase gallery
  viseme_demo.py            Deepgram TTS/STT audio demo → outputs/viseme_demo.html
  lipsync_pipeline.py       Deepgram TTS → Whisper → CMUdict → viseme timeline
  flashimage_generate.py    Gemini 2.5 Flash Image → 15 identity-locked viseme stills
  extract_landmarks.py      MediaPipe landmarks + alignment + triangulation → geometry.json

webapp/
  server.py                 FastAPI server (port 7432) — head generation + audio APIs
  index.html                Single-page head studio (gallery + demo + custom sentences)

docs/
  flutter_integration.md    Flutter + voice-gateway integration guide
  talking-head-options.md   Research notes on talking-head model options

models/
  face_landmarker.task      MediaPipe FaceLandmarker model (downloaded)

outputs/
  heads/                    Claude-generated SVG heads (one dir per character)
    young_man/              15 SVGs + gallery.html
    young_woman/
    …
  viseme_demo.html          Standalone audio-driven lip-sync demo
  viseme_cache/             Cached TTS audio + STT timelines (keyed by sentence)
  lipsync/
    audio.mp3               Generated TTS audio (Whisper pipeline)
    lipsync_data.js         Viseme timeline (loaded by both demos)
  flashimage/
    base.png, <viseme>.png  Flash Image base + 15 viseme stills
    manifest.json           viseme → filename map
    geometry.json           aligned landmarks + triangles (consumed by morph_demo.html)

avatar_demo/                Flutter macOS app (parametric SVG approach)
  lib/main.dart             Full CustomPainter implementation + AudioPlayer + Ticker
  assets/
    audio/audio.mp3         Bundled TTS audio
    data/lipsync_data.json  Bundled viseme timeline

runpod/                     RunPod / ComfyUI AI video generation pipeline
  pod.py                    Pod lifecycle management
  generate_sample.py        T2V smoke test
  generate_viseme.py        T2V viseme sequence (single pass)
  generate_viseme_i2v.py    4-phase I2V pipeline (consistent avatar)
  generate_fantasy_talking.py  Audio-driven lip sync via FantasyTalking
  core/
    comfyui_client.py       ComfyUI REST client
    wan_workflow.py         Wan 2.2 T2V workflow builder
  docs/
    runpod-video.md         RunPod + Wan 2.2 deployment spec
    runpod-audio.md         Audio generation model research
```

## Setup

```bash
# Env vars (in .env — not committed)
ANTHROPIC_API_KEY=...     # for Claude SVG generation
DEEPGRAM_API_KEY=...      # for TTS + STT timestamps
OPENROUTER_API_KEY=...    # alternative to ANTHROPIC_API_KEY; also for Flash Image
RUNPOD_API_KEY=...
RUNPOD_POD_ID=...
COMFYUI_URL=...           # set after starting the pod

# ── Claude SVG head generation ──────────────────────────────────────────────
pip install anthropic

# Generate a single character (15 viseme SVGs)
python scripts/generate_head.py --preset young_woman
python scripts/generate_head.py --style "robot with glowing eyes, teal accent, flat design"

# Generate all 6 preset characters
python scripts/generate_heads_batch.py --skip-existing

# Audio-driven demo (requires DEEPGRAM_API_KEY)
python scripts/viseme_demo.py
open outputs/viseme_demo.html

# ── Head studio web app ───────────────────────────────────────────────────
pip install fastapi "uvicorn[standard]"
python webapp/server.py
open http://localhost:7432

# ── Flash Image + MediaPipe morph demo ───────────────────────────────────
python scripts/flashimage_generate.py                 # generate 15 viseme stills (~$0.60)
python scripts/flashimage_generate.py blink           # eyes-closed still for the idle blink
uv venv --python 3.12 .venv-landmarks                 # MediaPipe needs Python <=3.12
uv pip install --python .venv-landmarks/bin/python mediapipe opencv-python-headless numpy scipy
.venv-landmarks/bin/python scripts/extract_landmarks.py
python3 -m http.server 8765                           # serve over http:// (canvas pixel access)
open http://localhost:8765/morph_demo.html

# ── Parametric SVG demo ───────────────────────────────────────────────────
pip install requests openai-whisper nltk
python scripts/lipsync_pipeline.py
open demo.html

# ── Flutter macOS app ─────────────────────────────────────────────────────
cd avatar_demo && flutter run -d macos

# ── RunPod avatar generation ──────────────────────────────────────────────
python runpod/pod.py start
export COMFYUI_URL=$(python runpod/pod.py url)
python runpod/generate_viseme_i2v.py
python runpod/generate_fantasy_talking.py outputs/lipsync/audio.mp3
```
