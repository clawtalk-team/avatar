#!/usr/bin/env python3
"""
ClaWTalk Head Studio — local web server
----------------------------------------
Serves the head generation and preview web app.

  python webapp/server.py          # starts on http://localhost:7432
  python webapp/server.py --port 8080
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# ── Load .env ────────────────────────────────────────────────────────────────
env_file = REPO_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "fastapi", "uvicorn[standard]"], check=True)
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn

from pydantic import BaseModel
from typing import Optional

# Import generation helpers
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import generate_head as gh

# Deepgram helpers (from viseme_demo.py)
def _load_viseme_demo():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "viseme_demo", REPO_ROOT / "scripts" / "viseme_demo.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
vd = _load_viseme_demo()

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="ClaWTalk Head Studio")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HEADS_DIR = REPO_ROOT / "outputs" / "heads"
HEADS_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_CACHE = REPO_ROOT / "outputs" / "webapp_cache"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

# ── Models ────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    style: str
    name: Optional[str] = None
    preset: Optional[str] = None
    model: str = "claude-opus-4-6"

class SpeakRequest(BaseModel):
    text: str
    head: str  # name of head directory

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = Path(__file__).parent / "index.html"
    return html_file.read_text()


@app.get("/api/heads")
async def list_heads():
    """List all generated head directories."""
    heads = []
    for d in sorted(HEADS_DIR.iterdir()):
        if d.is_dir():
            svgs = list(d.glob("*.svg"))
            sil = d / "sil.svg"
            heads.append({
                "name": d.name,
                "visemes": len(svgs),
                "complete": len(svgs) >= 15,
                "sil_svg": sil.read_text() if sil.exists() else None,
            })
    return heads


@app.get("/api/presets")
async def list_presets():
    return [{"key": k, "description": v} for k, v in gh.PRESETS.items()]


@app.post("/api/generate")
async def generate_head(req: GenerateRequest):
    """Generate a set of viseme SVGs for a character (runs synchronously, may take a while)."""
    if req.preset and req.preset in gh.PRESETS:
        style = gh.PRESETS[req.preset]
        name = req.name or req.preset
    elif req.style:
        style = req.style
        name = req.name or re.sub(r"[^a-z0-9]+", "_", style[:40].lower()).strip("_")
    else:
        raise HTTPException(400, "Provide style or preset")

    try:
        gallery = gh.generate(
            style=style, name=name, visemes=gh.ALL_VISEMES,
            model=req.model, out_root=HEADS_DIR, skip_existing=True,
        )
        return {"name": name, "gallery": f"/heads/{name}/gallery.html", "ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/head/{name}/svgs")
async def get_head_svgs(name: str):
    """Return all SVGs for a head as a dict."""
    head_dir = HEADS_DIR / name
    if not head_dir.exists():
        raise HTTPException(404, "Head not found")
    svgs = {}
    for v in gh.VISEMES:
        f = head_dir / f"{v}.svg"
        if f.exists():
            svgs[v] = f.read_text()
    return svgs


@app.post("/api/speak")
async def speak(req: SpeakRequest):
    """Generate TTS audio and word-level viseme timeline."""
    api_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "DEEPGRAM_API_KEY not set")

    cache_key = re.sub(r"[^a-z0-9]+", "_", req.text[:60].lower()).strip("_")
    audio_file = AUDIO_CACHE / f"{cache_key}.mp3"
    timeline_file = AUDIO_CACHE / f"{cache_key}.json"

    if not audio_file.exists():
        try:
            audio_bytes = vd.deepgram_tts(req.text, api_key)
            audio_file.write_bytes(audio_bytes)
        except Exception as e:
            raise HTTPException(500, f"TTS failed: {e}")

    if not timeline_file.exists():
        try:
            audio_bytes = audio_file.read_bytes()
            words = vd.deepgram_stt_words(audio_bytes, api_key)
            timeline = vd.words_to_timeline(words)
            timeline_file.write_text(json.dumps(timeline))
        except Exception as e:
            raise HTTPException(500, f"STT failed: {e}")

    timeline = json.loads(timeline_file.read_text())
    # Return audio as base64 + timeline
    import base64
    audio_b64 = base64.b64encode(audio_file.read_bytes()).decode()
    return {"audio_b64": audio_b64, "timeline": timeline, "text": req.text}


# Serve SVG files
@app.get("/heads/{name}/{file}")
async def serve_head_file(name: str, file: str):
    f = HEADS_DIR / name / file
    if not f.exists():
        raise HTTPException(404)
    media = "image/svg+xml" if file.endswith(".svg") else "text/html"
    return FileResponse(f, media_type=media)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7432)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    print(f"\nClaWTalk Head Studio → http://{args.host}:{args.port}\n")
    uvicorn.run(app, host=args.host, port=args.port)
