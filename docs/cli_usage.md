# Voxhelm CLI Reference

## Installation

```bash
cd photo-generation
pip install -e .            # core (Anthropic API, Typer, FastAPI)
pip install -e ".[all]"     # + Bedrock (boto3) + OpenRouter (openai)
```

## Environment Variables

Set in `.env` at the project root (gitignored):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | One of these | Anthropic API key (direct) |
| `OPENROUTER_API_KEY` | One of these | OpenRouter API key |
| AWS credentials | One of these | For Bedrock (boto3 auto-detection) |
| `DEEPGRAM_API_KEY` | For `speak` | Deepgram API key (TTS + STT) |
| `AWS_BEDROCK_REGION` | Optional | Bedrock region (default: ap-southeast-2) |

API priority: **Bedrock** (if AWS creds, no ANTHROPIC_API_KEY) → **Anthropic direct** → **OpenRouter**.

---

## Commands

### `voxhelm generate`

Generate a set of 15 viseme SVGs for a character.

```bash
# From a preset
voxhelm generate --preset young_woman

# Custom style
voxhelm generate --style "robot with glowing eyes, teal accents, flat design" --name robot

# Resume an interrupted run
voxhelm generate --preset young_woman --skip-existing

# List available presets
voxhelm generate --list-presets

# Use a different model
voxhelm generate --preset young_woman --model claude-sonnet-4-6
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--preset` | | Bundled character preset |
| `--style` | | Custom style description |
| `--name` | derived | Output directory name |
| `--model` | claude-opus-4-6 | Claude model |
| `--out` | outputs/heads | Root output directory |
| `--skip-existing` | false | Skip visemes with existing SVG files |
| `--verbose` / `-v` | false | Debug logging |

**Output:** `outputs/heads/<name>/` containing `sil.svg` through `U.svg` (15 files)
plus `gallery.html`. Opens the gallery in your browser when done.

**Presets:** young_man, middle_man, older_man, young_woman, middle_woman, older_woman.

---

### `voxhelm speak`

Generate TTS audio with a viseme timeline and open a playback demo.

```bash
voxhelm speak --head young_woman --text "Hello world, how are you today?"
voxhelm speak --head young_woman --text "The quick brown fox" --out my_demo.html
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--head` | required | Head name (directory in outputs/heads/) |
| `--text` | required | Text to speak |
| `--out` | outputs/speak_demo.html | Output HTML path |
| `--verbose` / `-v` | false | Debug logging |

**Requires:** `DEEPGRAM_API_KEY` in `.env`.

**Pipeline:** Deepgram TTS (aura-2-thalia-en) → Deepgram STT (nova-3) → CMUdict
phoneme lookup → viseme timeline. Audio and timeline are embedded in a self-contained
HTML file that plays back with speed controls and blink animation.

---

### `voxhelm validate`

Launch a web viewer to visually validate a generated head.

```bash
voxhelm validate --head young_woman
voxhelm validate --head young_woman --port 8080
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--head` | required | Head name to validate |
| `--port` | auto | Port for local web server |
| `--verbose` / `-v` | false | Debug logging |

Opens a browser with:
- **Gallery tab:** All 15 visemes in a grid (shows missing frames)
- **Preview tab:** Click any viseme to see it full-size. Press Space to auto-cycle.
- **Blink overlay:** Validates blink animation rendering

Press Ctrl+C to stop the server.

---

### `voxhelm serve`

Start the Voxhelm web studio (full generation + preview UI).

```bash
voxhelm serve
voxhelm serve --port 8080 --host 0.0.0.0
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 7432 | Server port |
| `--host` | 127.0.0.1 | Server host |
| `--verbose` / `-v` | false | Debug logging |

This is the same web studio as `webapp/server.py` but backed by the
`voxhelm.core` library for all generation and audio processing.

**API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/heads` | List all generated heads |
| GET | `/api/presets` | List bundled presets |
| POST | `/api/generate` | Generate a head (body: `{style, name?, preset?, model}`) |
| GET | `/api/head/{name}/svgs` | Get all SVGs for a head as JSON dict |
| POST | `/api/speak` | Generate TTS + timeline (body: `{text, head}`) |

---

## Using as a Library

The core functions are importable for use in your own scripts or servers:

```python
from voxhelm import load_env
from voxhelm.core.presets import PRESETS, get_preset
from voxhelm.core.generator import generate, load_svgs
from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
from voxhelm.core.timeline import words_to_timeline
from voxhelm.core.api_client import get_llm_client

load_env()  # Load .env file

# Generate SVGs
gallery = generate(
    style=get_preset("young_woman"),
    name="young_woman",
    skip_existing=True,
)

# Generate audio + timeline
audio = deepgram_tts("Hello world")
words = deepgram_stt_words(audio)
timeline = words_to_timeline(words)

# Load SVGs as dict
svgs = load_svgs(Path("outputs/heads/young_woman"))
```

## Server Integration (FastAPI)

```python
from voxhelm.server.app import create_app

app = create_app()
# Mount in your existing app, or run directly:
# uvicorn.run(app, port=7432)
```
