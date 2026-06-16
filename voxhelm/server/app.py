"""Voxhelm web studio — FastAPI server wrapping core library."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Optional

from voxhelm import REPO_ROOT


def create_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    from voxhelm.core.presets import PRESETS
    from voxhelm.core.visemes import ALL_VISEMES
    from voxhelm.core import generator as gen
    from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
    from voxhelm.core.timeline import words_to_timeline

    app = FastAPI(title="Voxhelm Studio")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    HEADS_DIR = REPO_ROOT / "outputs" / "heads"
    HEADS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE = REPO_ROOT / "outputs" / "webapp_cache"
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

    class GenerateRequest(BaseModel):
        style: str
        name: Optional[str] = None
        preset: Optional[str] = None
        model: str = "claude-opus-4-6"

    class SpeakRequest(BaseModel):
        text: str
        head: str

    @app.get("/", response_class=HTMLResponse)
    async def root():
        html_file = REPO_ROOT / "webapp" / "index.html"
        return html_file.read_text()

    @app.get("/api/heads")
    async def list_heads():
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
        return [{"key": k, "description": v} for k, v in PRESETS.items()]

    @app.post("/api/generate")
    async def generate_head(req: GenerateRequest):
        if req.preset and req.preset in PRESETS:
            style = PRESETS[req.preset]
            name = req.name or req.preset
        elif req.style:
            style = req.style
            name = req.name or re.sub(r"[^a-z0-9]+", "_", style[:40].lower()).strip("_")
        else:
            raise HTTPException(400, "Provide style or preset")

        try:
            gallery = gen.generate(
                style=style,
                name=name,
                out_root=HEADS_DIR,
                model=req.model,
                skip_existing=True,
            )
            return {"name": name, "gallery": f"/heads/{name}/gallery.html", "ok": True}
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.get("/api/head/{name}/svgs")
    async def get_head_svgs(name: str):
        head_dir = HEADS_DIR / name
        if not head_dir.exists():
            raise HTTPException(404, "Head not found")
        svgs = {}
        for v in ALL_VISEMES:
            f = head_dir / f"{v}.svg"
            if f.exists():
                svgs[v] = f.read_text()
        return svgs

    @app.post("/api/speak")
    async def speak(req: SpeakRequest):
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            raise HTTPException(500, "DEEPGRAM_API_KEY not set")

        cache_key = re.sub(r"[^a-z0-9]+", "_", req.text[:60].lower()).strip("_")
        audio_file = AUDIO_CACHE / f"{cache_key}.mp3"
        timeline_file = AUDIO_CACHE / f"{cache_key}.json"

        if not audio_file.exists():
            try:
                audio_bytes = deepgram_tts(req.text, api_key)
                audio_file.write_bytes(audio_bytes)
            except Exception as e:
                raise HTTPException(500, f"TTS failed: {e}")

        if not timeline_file.exists():
            try:
                audio_bytes = audio_file.read_bytes()
                words = deepgram_stt_words(audio_bytes, api_key)
                timeline = words_to_timeline(words)
                timeline_file.write_text(json.dumps(timeline))
            except Exception as e:
                raise HTTPException(500, f"STT failed: {e}")

        timeline = json.loads(timeline_file.read_text())
        audio_b64 = base64.b64encode(audio_file.read_bytes()).decode()
        return {"audio_b64": audio_b64, "timeline": timeline, "text": req.text}

    @app.get("/heads/{name}/{file}")
    async def serve_head_file(name: str, file: str):
        f = HEADS_DIR / name / file
        if not f.exists():
            raise HTTPException(404)
        media = "image/svg+xml" if file.endswith(".svg") else "text/html"
        return FileResponse(f, media_type=media)

    return app
