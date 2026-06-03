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

## Current state

| Component | Status |
|-----------|--------|
| SVG parametric cartoon | Working — `demo.html` |
| Deepgram TTS | Working — `outputs/lipsync/audio.mp3` |
| Whisper word timestamps | Working |
| CMUdict viseme mapping | Working |
| Smoothstep transitions | Working |
| Browser lipsync demo | Working — open `demo.html` |
| Flutter macOS app | Working — `avatar_demo/` |
| RunPod infrastructure | Implemented, not yet run on live pod |
| Wan 2.2 T2V avatar | Not yet generated |
| Wan 2.2 I2V viseme pipeline | Not yet generated |
| FantasyTalking lipsync | Not yet generated |

---

## Planned

### Near term

**End-to-end real avatar pipeline:**
1. Start the RunPod pod
2. Run `generate_viseme_i2v.py` to produce the photorealistic SIL portrait
3. Feed `outputs/lipsync/audio.mp3` (from the Deepgram TTS pipeline) into
   `generate_fantasy_talking.py` with the SIL portrait as input
4. The result is a photorealistic talking head video synced to the TTS audio

**Replace SVG cartoon in demo:**
Once FantasyTalking output is satisfactory, replace the SVG avatar in `demo.html`
with either a `<video>` element (pre-generated) or a composited approach where the
AI-generated face is composited over the parametric mouth (preserving the real-time
capability while upgrading the face quality).

### Longer term

**Real-time inference:** FantasyTalking and the full Wan 2.2 pipeline are
batch-oriented (minutes per clip on an RTX 6000). For a real-time talking avatar,
the options are:
- **Pre-generate per sentence** — generate a video for each likely TTS utterance and
  cache it. Acceptable for a limited-vocabulary app.
- **Faster models** — lighter audio-driven talking head models (SadTalker, Hallo, etc.)
  trade quality for speed. Some run near-real-time on consumer hardware.
- **Hybrid** — keep the parametric SVG mouth for real-time response but composite it
  over a static AI-generated portrait (blending the two approaches).

**Flutter integration:** Feed the FantasyTalking video output into the Flutter app as
a `VideoPlayerController` asset, replacing the `CustomPainter` mouth with the real video.
The parametric implementation remains available as a fallback for low-latency scenarios.

**Full viseme set coverage:** The I2V pipeline currently demonstrates SIL, PP, and FF.
Extend to the full 15-viseme set for higher accuracy, particularly for vowels (aa, E, I,
O, U have very distinct mouth shapes that are noticeable when wrong).

---

## Project structure

```
demo.html                   Browser lipsync demo (SVG cartoon + Deepgram audio)
svg_generator.py            Parametric SVG face generator (15 visemes)
generator.py                Original SD inpainting approach (abandoned)

scripts/
  lipsync_pipeline.py       Deepgram TTS → Whisper → CMUdict → viseme timeline

outputs/
  lipsync/
    audio.mp3               Generated TTS audio
    lipsync_data.js         Viseme timeline (loaded by demo.html)
  svg_visemes/              Generated SVG face frames

avatar_demo/                Flutter macOS app
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
# Python deps for lipsync pipeline
pip install requests openai-whisper nltk --break-system-packages

# Env vars (in .env — not committed)
DEEPGRAM_API_KEY=...
RUNPOD_API_KEY=...
RUNPOD_POD_ID=...
COMFYUI_URL=...    # set after starting the pod

# Run lipsync pipeline
python scripts/lipsync_pipeline.py

# Open browser demo
open demo.html

# Run Flutter app (macOS)
cd avatar_demo && flutter run -d macos

# RunPod avatar generation
python runpod/pod.py start
export COMFYUI_URL=$(python runpod/pod.py url)
python runpod/generate_viseme_i2v.py
python runpod/generate_fantasy_talking.py outputs/lipsync/audio.mp3
```
