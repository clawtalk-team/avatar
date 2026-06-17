# Voxhelm CLI Reference

## Installation

```bash
pip install -e ".[all]"    # install with all backends
voxhelm --help             # verify
```

Or run without installing:

```bash
uv run --extra all python -m voxhelm --help
```

## Workflow

The recommended workflow is:

1. **`voxhelm generate-base`** — create the reference frame (sil)
2. **`voxhelm validate`** — inspect the base in a web viewer
3. **`voxhelm generate-visemes`** — generate the remaining 14 viseme frames
4. **`voxhelm speak`** — create an audio-driven demo

For quick iteration, `voxhelm generate` runs steps 1 + 3 in one shot.

---

## Commands

### `voxhelm generate-base`

Generate the base (sil) frame for a character. Creates a single reference frame
for review before generating all 15 visemes.

```
Options:
  --mode TEXT         Generation mode: svg (cartoon) or photo (photorealistic) [default: svg]
  --preset TEXT       Use a bundled character preset
  --prompt TEXT        Character description prompt
  --name TEXT         Output directory name
  --list-presets      List available presets
  --model TEXT        Claude model (svg mode only) [default: claude-opus-4-6]
  --out TEXT          Root output directory [default: outputs/heads]
  -v, --verbose
```

Examples:

```bash
# SVG cartoon from preset
voxhelm generate-base --preset young_woman

# Photorealistic from custom description
voxhelm generate-base --mode photo --prompt "woman in her 30s, dark hair, olive skin" --name photo_woman

# List all presets
voxhelm generate-base --list-presets
```

---

### `voxhelm generate-visemes`

Generate the remaining 14 viseme frames from an approved base. Reads mode and
style from the metadata saved by `generate-base`.

```
Options:
  --head TEXT         Head name (from generate-base) [required]
  --out TEXT          Root output directory [default: outputs/heads]
  --skip-existing     Skip visemes that already exist [default: true]
  --no-blink          Skip blink frame (photo mode)
  -v, --verbose
```

Examples:

```bash
voxhelm generate-visemes --head young_woman
voxhelm generate-visemes --head photo_woman --no-blink
```

---

### `voxhelm generate`

Generate all 15 viseme assets in one shot (base + visemes). For more control,
use `generate-base` + `generate-visemes` instead.

```
Options:
  --mode TEXT         Generation mode: svg or photo [default: svg]
  --preset TEXT       Use a bundled character preset
  --prompt TEXT        Character description prompt
  --name TEXT         Output directory name
  --list-presets      List available presets
  --model TEXT        Claude model (svg mode only) [default: claude-opus-4-6]
  --out TEXT          Root output directory [default: outputs/heads]
  --skip-existing     Skip existing assets
  --no-blink          Skip blink frame (photo mode)
  -v, --verbose
```

Examples:

```bash
# One-shot SVG generation
voxhelm generate --preset young_woman

# One-shot photo generation
voxhelm generate --mode photo --prompt "friendly man, 40s, short beard" --name bearded_man
```

---

### `voxhelm speak`

Generate TTS audio with viseme timeline and write a self-contained playback HTML demo.
Auto-detects whether the head uses SVG or PNG assets.

```
Options:
  --head TEXT         Head name (directory in outputs/heads/) [required]
  --text TEXT         Text to speak [required]
  --out TEXT          Output HTML path [default: outputs/speak_demo.html]
  -v, --verbose
```

Requires `DEEPGRAM_API_KEY` in `.env`.

Examples:

```bash
voxhelm speak --head young_woman --text "Hello, welcome aboard!"
voxhelm speak --head photo_woman --text "Nice to meet you" --out demo.html
```

---

### `voxhelm validate`

Launch a web viewer to validate generated assets. Shows all viseme frames in
a gallery with preview and blink animation.

```
Options:
  --head TEXT         Head name to validate [required]
  --port INTEGER      Port for web viewer (0=auto) [default: 0]
  -v, --verbose
```

Examples:

```bash
voxhelm validate --head young_woman
voxhelm validate --head photo_woman --port 8080
```

Press Ctrl+C to stop the server.

---

### `voxhelm serve`

Start the Voxhelm web studio — a FastAPI server with generation, preview, and
playback functionality.

```
Options:
  --port INTEGER      Server port [default: 7432]
  --host TEXT         Server host [default: 127.0.0.1]
  -v, --verbose
```

API endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/presets` | List character presets |
| `GET` | `/api/heads` | List all generated heads |
| `POST` | `/api/generate-base` | Generate base frame (sync) |
| `POST` | `/api/generate-visemes` | Generate visemes (async, returns job ID) |
| `POST` | `/api/generate` | One-shot: base + visemes |
| `GET` | `/api/jobs/{id}` | Poll job status |
| `GET` | `/api/jobs/{id}/stream` | SSE stream of generation progress |
| `GET` | `/api/head/{name}/assets` | Get all viseme assets + extras |
| `GET` | `/api/head/{name}/validate` | Get validation gallery HTML |
| `DELETE` | `/api/head/{name}` | Delete a head and all its assets |
| `POST` | `/api/speak` | TTS + viseme timeline |

---

## Environment variables

Set in `.env` at the project root:

| Variable | Required for | Description |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | SVG mode | Anthropic API key |
| `OPENROUTER_API_KEY` | Photo mode, or as SVG fallback | OpenRouter API key |
| `DEEPGRAM_API_KEY` | `speak` command | Deepgram API key for TTS/STT |
| `AWS_BEDROCK_REGION` | Bedrock backend | AWS region (default: ap-southeast-2) |

SVG mode tries backends in order: AWS Bedrock → Anthropic direct → OpenRouter.

## Character presets

| Key | Description |
|-----|-------------|
| `young_man` | Young man, mid-20s, short dark hair, light skin, clean-shaven |
| `middle_man` | Middle-aged man, 40s, salt-and-pepper stubble, medium-brown skin |
| `older_man` | Elderly man, 70s, white hair, weathered warm skin, kind eyes |
| `young_woman` | Young woman, mid-20s, long auburn hair, fair freckled skin |
| `middle_woman` | Middle-aged woman, 40s, dark hair with grey streaks, medium-brown skin |
| `older_woman` | Elderly woman, 70s, silver bun, light wrinkled skin, rosy cheeks |

---

## Using as a Library

```python
from voxhelm import load_env
from voxhelm.core.generator import generate_base, generate_visemes, load_svgs
from voxhelm.core.photo_generator import generate_base as photo_base
from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
from voxhelm.core.timeline import words_to_timeline
from voxhelm.server.app import create_app  # FastAPI app factory

load_env()

# SVG workflow
base = generate_base(style="young woman, cartoon", name="test")
gallery = generate_visemes(style="young woman, cartoon", name="test")
svgs = load_svgs(Path("outputs/heads/test"))

# Photo workflow
photo_base(style="woman, 30s, dark hair", name="photo_test")

# Audio + timeline
audio = deepgram_tts("Hello world")
words = deepgram_stt_words(audio)
timeline = words_to_timeline(words)
```
