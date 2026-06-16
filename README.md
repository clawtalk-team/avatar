# Voxhelm

Avatar generation and audio-driven lip-sync toolkit. Generate cartoon SVG or
photorealistic PNG talking avatars from a text description, then animate them
with audio-synced viseme playback.

## Features

- **Two rendering modes:** SVG cartoon (Claude) and photorealistic PNG (Gemini Flash Image)
- **15 OVR visemes** per character with identity-locked generation
- **Audio-driven animation** via Deepgram TTS/STT + phoneme-to-viseme mapping
- **Split workflow:** generate base → review → generate visemes
- **Web studio** for generation, preview, and playback
- **API-ready** FastAPI server with REST endpoints
- **Flutter widget** for mobile/desktop integration (`voxhelm_avatar` package)

## Install

```bash
# Clone and install
git clone <repo-url>
cd photo-generation
pip install -e ".[all]"
```

### Optional dependencies

The base install includes the CLI and server. Generation backends are optional:

```bash
pip install -e ".[svg]"        # Claude API for SVG generation
pip install -e ".[bedrock]"    # AWS Bedrock backend
pip install -e ".[openrouter]" # OpenRouter backend (also needed for photo mode)
pip install -e ".[all]"        # Everything
```

### Environment variables

Create a `.env` file in the project root:

```bash
# At least one of these for SVG mode:
ANTHROPIC_API_KEY=sk-ant-...        # Anthropic direct
# or configure AWS credentials for Bedrock
# or:
OPENROUTER_API_KEY=sk-or-...        # OpenRouter (also required for photo mode)

# For audio (speak command):
DEEPGRAM_API_KEY=...
```

## Quick start

### Generate an avatar

```bash
# SVG cartoon (default)
voxhelm generate --preset young_woman
voxhelm generate --style "robot with teal accents" --name bot

# Photorealistic PNG
voxhelm generate --mode photo --style "woman in her 30s, dark hair, olive skin" --name photo_woman

# List available presets
voxhelm generate --list-presets
```

### Split workflow (recommended for quality control)

```bash
# Step 1: Generate just the base frame
voxhelm generate-base --mode photo --style "friendly man, 40s, short beard" --name bearded_man

# Step 2: Review the base in the gallery (opens automatically)

# Step 3: Generate remaining 14 visemes from the approved base
voxhelm generate-visemes --head bearded_man
```

### Audio-driven demo

```bash
# Create a playback demo with TTS audio
voxhelm speak --head young_woman --text "Hello, welcome aboard!"

# Opens a self-contained HTML file with audio + viseme animation
```

### Validate and preview

```bash
voxhelm validate --head young_woman    # Web viewer for all viseme frames
voxhelm serve                          # Full web studio on http://localhost:7432
```

## API server

The FastAPI server exposes the same functionality as the CLI:

```bash
voxhelm serve --port 7432
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/heads` | List all generated heads |
| `GET` | `/api/presets` | List character presets |
| `POST` | `/api/generate-base` | Generate base frame |
| `POST` | `/api/generate-visemes` | Generate visemes from approved base |
| `GET` | `/api/head/{name}/assets` | Get all viseme assets for a head |
| `POST` | `/api/speak` | TTS + viseme timeline |

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
svgs = load_svgs(Path("outputs/heads/test"))

# Photo generation
photo_base(style="woman, 30s, dark hair", name="photo_test")
```

## Flutter package

The `voxhelm_avatar` Flutter package provides a drop-in widget:

```dart
import 'package:voxhelm_avatar/voxhelm_avatar.dart';

final visemeSet = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');
final ctrl = VisemeController()..setTimeline(timeline);
final blink = BlinkController()..start();

VoxhelmAvatar(visemeSet: visemeSet, controller: ctrl, blinkController: blink, size: 200)
```

See `voxhelm_avatar/README.md` for the full API reference.

## Legacy scripts

Standalone scripts from earlier development are in `scripts/`. These still work
but the voxhelm CLI is the recommended interface.

### Requirements for legacy scripts

```bash
# Lipsync pipeline (Whisper + NLTK)
pip install -r requirements-scripts.txt
python scripts/lipsync_pipeline.py

# MediaPipe landmark extraction (needs Python <=3.12)
uv venv --python 3.12 .venv-landmarks
uv pip install --python .venv-landmarks/bin/python -r requirements-landmarks.txt
.venv-landmarks/bin/python scripts/extract_landmarks.py
```

## Project structure

```
voxhelm/                    Python package — CLI + core library + server
  cli/main.py               Typer CLI
  core/
    generator.py             SVG cartoon generation (Claude)
    photo_generator.py       Photorealistic PNG generation (Gemini Flash)
    api_client.py            LLM client factory (Bedrock/Anthropic/OpenRouter)
    audio.py                 Deepgram TTS/STT
    timeline.py              Phoneme → viseme timeline
    visemes.py               15 OVR viseme definitions + mappings
    presets.py               Bundled character presets
  server/app.py             FastAPI server
  viewer/viewer.html        Validation web viewer

voxhelm_avatar/             Flutter package — drop-in avatar widget

scripts/                    Legacy standalone scripts
docs/                       Research notes and experiment history
outputs/                    Generated assets (not committed)
```

## Documentation

- `docs/experiments.md` — Research history and approaches tried
- `docs/flutter_integration.md` — Flutter + voice-gateway integration guide
- `docs/cli_usage.md` — Full CLI reference
- `docs/talking-head-options.md` — Talking-head model research notes
