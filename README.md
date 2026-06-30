# Voxhelm

Avatar generation and audio-driven lip-sync toolkit. Generate cartoon SVG or
photorealistic PNG talking avatars from a text description, then animate them
with audio-synced viseme playback.

## Features

- **Two rendering modes:** SVG cartoon (via Claude) and photorealistic PNG (via Gemini Flash Image)
- **15 OVR visemes** per character with identity-locked generation
- **14 bundled presets** — people, robots, and fantasy characters
- **Animation modes** — idle, listening, thinking videos via Veo 3.1 Lite
- **Audio-driven lip-sync** via Deepgram TTS/STT + phoneme-to-viseme mapping
- **Split workflow:** generate base → review → generate visemes → animations
- **Proof page** — self-contained HTML with viseme grid, animation previews, and costs
- **CDN delivery** — assets served from `avatars.voxhelm.com` via CloudFront
- **Web studio** for generation, preview, and playback
- **API-ready** FastAPI server with REST endpoints
- **Flutter widget** for mobile/desktop integration (`voxhelm_avatar` package)
- **Export command** — package heads into Flutter apps with auto pubspec registration

---

## Install

```bash
git clone <repo-url>
cd photo-generation
pip install -e ".[all]"
```

This installs the `voxhelm` CLI command and all generation backends. The
`pyproject.toml` defines the package, its dependencies, and the CLI entry point.

### Optional dependency groups

```bash
pip install -e .               # Core only (CLI + server framework)
pip install -e ".[svg]"        # + Claude API (anthropic) for SVG generation
pip install -e ".[bedrock]"    # + AWS Bedrock backend (boto3)
pip install -e ".[openrouter]" # + OpenRouter backend (also needed for photo mode)
pip install -e ".[all]"        # Everything
```

### Environment variables

Create a `.env` file in the project root:

```bash
# SVG mode — at least one of:
ANTHROPIC_API_KEY=sk-ant-...          # Anthropic direct
# or configure AWS credentials        # for Bedrock
OPENROUTER_API_KEY=sk-or-...          # OpenRouter (also required for photo mode)

# Audio (speak command):
DEEPGRAM_API_KEY=...

# Optional:
AWS_BEDROCK_REGION=ap-southeast-2     # Bedrock region (default)
```

SVG mode tries backends in order: **Bedrock → Anthropic direct → OpenRouter**.

---

## Workflow

The recommended workflow is:

```
1. generate-base    →  create reference frame (sil)
2. validate         →  review in web viewer
3. generate-visemes →  generate remaining 14 frames
4. generate-anims   →  generate idle/listening/thinking videos (~$0.20 each)
5. speak            →  create audio-driven demo
```

Or use `generate` for a one-shot pipeline (steps 1-4 + proof page).

### Quick start

```bash
# Step 1: Generate a base frame
voxhelm generate-base --preset young_woman

# Step 2: Review (opens in browser automatically)

# Step 3: Generate all visemes
voxhelm generate-visemes --head young_woman

# Step 4: Audio demo
voxhelm speak --head young_woman --text "Hello, welcome aboard!"
```

Or do it all in one shot:

```bash
voxhelm generate --preset young_woman
voxhelm generate --mode photo --prompt "woman in her 30s, dark hair" --name photo_woman
```

---

## CLI Reference

### `voxhelm generate-base`

Step 1: Generate the base (sil) frame for a character.

```
Options:
  --mode TEXT         svg (cartoon) or photo (photorealistic)  [default: svg]
  --preset TEXT       Bundled character preset
  --prompt TEXT        Character description prompt
  --name TEXT         Output directory name
  --list-presets      List available presets
  --model TEXT        Claude model, svg mode only  [default: claude-opus-4-6]
  --out TEXT          Root output directory  [default: outputs/heads]
  -v, --verbose
```

```bash
voxhelm generate-base --preset young_woman
voxhelm generate-base --mode photo --prompt "friendly man, 40s, short beard" --name bearded_man
voxhelm generate-base --list-presets
```

### `voxhelm generate-visemes`

Step 2: Generate the remaining 14 viseme frames from an approved base.
Reads mode/style from metadata saved by `generate-base`.

```
Options:
  --head TEXT         Head name from generate-base  [required]
  --out TEXT          Root output directory  [default: outputs/heads]
  --skip-existing     Skip existing visemes  [default: true]
  --no-blink          Skip blink frame, photo mode only
  -v, --verbose
```

```bash
voxhelm generate-visemes --head young_woman
voxhelm generate-visemes --head photo_woman --no-blink
```

### `voxhelm generate`

Full pipeline: base + visemes + animation videos + proof page. Generates all
assets in one shot and opens the proof page when done.

```
Options:
  --mode TEXT         svg or photo  [default: svg]
  --preset TEXT       Bundled character preset
  --prompt TEXT        Character description prompt
  --name TEXT         Output directory name
  --list-presets      List available presets
  --model TEXT        Claude model, svg mode only  [default: claude-opus-4-6]
  --out TEXT          Root output directory  [default: outputs/heads]
  --skip-existing     Skip existing assets
  --no-blink          Skip blink frame, photo mode only
  -v, --verbose
```

```bash
voxhelm generate --preset young_woman
voxhelm generate --mode photo --prompt "woman in her 30s, dark hair" --name photo_woman
voxhelm generate --list-presets    # show all 14 presets
```

### `voxhelm generate-anims`

Generate animation videos (idle/listening/thinking) for an existing head.
Each mode costs ~$0.20 via Veo 3.1 Lite on OpenRouter.

```
Options:
  --head TEXT         Head name  [required]
  --modes TEXT        Comma-separated modes  [default: idle,listening,thinking]
  --out TEXT          Root output directory  [default: outputs/heads]
  --skip-existing     Skip modes that already have MP4s
  -v, --verbose
```

```bash
voxhelm generate-anims --head young_woman
voxhelm generate-anims --head young_woman --modes listening,thinking
voxhelm generate-anims --head young_woman --skip-existing
```

### `voxhelm export`

Package a generated head into a Flutter app's assets directory and register
it in `pubspec.yaml`.

```
Options:
  --head TEXT         Head name  [required]
  --target TEXT       Flutter app directory  [default: ../flutter-app]
  --out TEXT          Root output directory  [default: outputs/heads]
  -v, --verbose
```

```bash
voxhelm export --head young_woman
voxhelm export --head chrome_bot --target /path/to/flutter-app
```

### `voxhelm speak`

Generate TTS audio with viseme timeline and write a self-contained playback HTML.
Auto-detects SVG or PNG assets.

```
Options:
  --head TEXT         Head name  [required]
  --text TEXT         Text to speak  [required]
  --out TEXT          Output HTML path  [default: outputs/speak_demo.html]
  -v, --verbose
```

```bash
voxhelm speak --head young_woman --text "Hello, welcome aboard!"
voxhelm speak --head photo_woman --text "Nice to meet you" --out demo.html
```

### `voxhelm validate`

Launch a web viewer to inspect generated assets. Shows all viseme frames in a
gallery with preview and blink animation.

```
Options:
  --head TEXT         Head name  [required]
  --port INTEGER      Port (0=auto)  [default: 0]
  -v, --verbose
```

```bash
voxhelm validate --head young_woman
```

### `voxhelm serve`

Start the Voxhelm web studio (FastAPI server).

```
Options:
  --port INTEGER      Server port  [default: 7432]
  --host TEXT         Server host  [default: 127.0.0.1]
  -v, --verbose
```

```bash
voxhelm serve
voxhelm serve --port 8080 --host 0.0.0.0
```

---

## API Server

```bash
voxhelm serve --port 7432
# OpenAPI docs at http://localhost:7432/docs
```

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/presets` | List character presets |
| `GET` | `/api/heads` | List all generated heads with metadata + animations |
| `POST` | `/api/generate-base` | Step 1: generate base frame |
| `POST` | `/api/generate-visemes` | Step 2: generate visemes (+ auto animations) |
| `POST` | `/api/generate` | One-shot: base + all visemes + animations |
| `POST` | `/api/generate-anim-video` | Generate animation video for a mode |
| `GET` | `/api/head/{name}/assets` | Get all viseme assets (SVG/PNG) |
| `GET` | `/api/head/{name}/anim-frames` | Get animation frames as base64 |
| `GET` | `/api/head/{name}/validate` | Get validation gallery HTML |
| `GET` | `/heads/{name}/{file}` | Serve raw files (PNG/SVG/MP4) |
| `POST` | `/api/speak` | TTS audio + viseme timeline |

Request bodies use `prompt` (or `preset`) + `mode` (`svg`/`photo`), matching the CLI.

### Python library

```python
from voxhelm import load_env
from voxhelm.core.generator import generate_base, generate_visemes, load_svgs
from voxhelm.core.photo_generator import generate_base as photo_base
from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
from voxhelm.core.timeline import words_to_timeline
from voxhelm.server.app import create_app  # FastAPI app factory

load_env()

# SVG generation
base = generate_base(style="young woman, cartoon", name="test")
gallery = generate_visemes(style="young woman, cartoon", name="test")

# Photo generation
photo_base(style="woman, 30s, dark hair", name="photo_test")
```

---

## Character presets

| Key | Description |
|-----|-------------|
| `young_man` | Young man, mid-20s, short dark hair, light skin |
| `middle_man` | Middle-aged man, 40s, salt-and-pepper stubble |
| `older_man` | Elderly man, 70s, white hair, kind eyes |
| `young_woman` | Young woman, mid-20s, long auburn hair, freckled skin |
| `middle_woman` | Middle-aged woman, 40s, dark hair with grey streaks |
| `older_woman` | Elderly woman, 70s, silver bun, rosy cheeks |
| `photo_man` | Photorealistic man, late 30s, short brown hair |
| `photo_woman` | Photorealistic woman, early 30s, blonde hair |
| `chrome_bot` | Retro robot, chrome head, glowing blue eyes |
| `bolt_bot` | Pastel-mint robot, heart-shaped LED eyes |
| `mossling` | Forest sprite, leafy green face, amber eyes |
| `clayton` | Clay golem, terracotta head, chunky features |
| `nimbus` | Cloud genie, fluffy blue head, wispy top |
| `clawford` | Cartoon lobster, red-orange shell, cartoon eyes |
| `friendly_robot` | Friendly robot, silver-grey head, glowing teal eyes |

---

## CDN Assets

All 14 preset heads are published to `avatars.voxhelm.com` via S3 + CloudFront.

```
https://avatars.voxhelm.com/heads/manifest.json          — catalogue
https://avatars.voxhelm.com/heads/{name}/sil.png          — silent frame
https://avatars.voxhelm.com/heads/{name}/{viseme}.png     — viseme frame
https://avatars.voxhelm.com/index.html                    — visual index
```

### Publishing

```bash
./scripts/publish-avatars.sh                    # publish all heads
./scripts/publish-avatars.sh friendly_robot     # publish specific head
./scripts/publish-avatars.sh --dry-run          # preview
```

---

## Flutter package

The `voxhelm_avatar` Flutter package provides a drop-in widget supporting
both SVG and PNG modes:

```dart
import 'package:voxhelm_avatar/voxhelm_avatar.dart';

// Load from CDN (recommended)
final visemeSet = VisemeSet.fromCdnUrl('https://avatars.voxhelm.com/heads/friendly_robot');

// Or load from API server
final visemeSet = await VisemeSet.fromUrl('http://localhost:7432/api/head/friendly_robot/svgs');

// Or load all heads from manifest
final allHeads = await VisemeSet.fromManifest('https://avatars.voxhelm.com/heads');

final ctrl = VisemeController()..setTimeline(timeline);
final blink = BlinkController()..start();

VoxhelmAvatar(visemeSet: visemeSet, controller: ctrl, blinkController: blink, size: 200)
```

See `voxhelm_avatar/README.md` for the full API reference.

---

## Legacy scripts

Standalone scripts from earlier development are in `scripts/legacy/`. The
`voxhelm` CLI is the recommended interface.

For scripts that still run independently (`scripts/`):

```bash
pip install -r requirements-scripts.txt      # Whisper + NLTK
pip install -r requirements-landmarks.txt    # MediaPipe (Python <=3.12 only)
```

---

## Project structure

```
voxhelm/                    Python package
  cli/main.py               Typer CLI (generate, generate-anims, export, speak, etc.)
  core/
    generator.py             SVG cartoon generation (Claude API)
    photo_generator.py       Photorealistic PNG generation (Gemini Flash Image)
    animations.py            Animation mode definitions + Veo video generation
    api_client.py            LLM client factory (Bedrock / Anthropic / OpenRouter)
    audio.py                 Deepgram TTS / STT
    timeline.py              Phoneme → viseme timeline
    visemes.py               15 OVR viseme definitions + mappings
    presets.py               14 bundled character presets
  server/app.py             FastAPI server
  viewer/viewer.html        Validation web viewer template

voxhelm_avatar/             Flutter package — drop-in avatar widget (SVG + PNG)
scripts/publish-avatars.sh  Publish heads to S3/CloudFront CDN
scripts/legacy/             Superseded scripts from earlier experiments
webapp/                     Web studio frontend (served by voxhelm serve)
docs/                       Documentation and experiment history
```

## Documentation

- `docs/cli_usage.md` — Full CLI reference with examples
- `docs/experiments.md` — Research history and approaches tried
- `docs/flutter_integration.md` — Flutter + voice-gateway integration guide
- `docs/talking-head-options.md` — Talking-head model research notes
