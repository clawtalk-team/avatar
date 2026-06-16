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
    from voxhelm.core import generator as svg_gen
    from voxhelm.core import photo_generator as photo_gen
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

    class GenerateBaseRequest(BaseModel):
        mode: str = "svg"
        style: str
        name: Optional[str] = None
        preset: Optional[str] = None
        model: str = "claude-opus-4-6"

    class GenerateVisemesRequest(BaseModel):
        head: str

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
                pngs = [f for f in d.glob("*.png") if f.name != "base.png"]
                mode = "svg" if svgs else "photo" if pngs else "unknown"
                asset_count = len(svgs) if mode == "svg" else len(pngs)

                # Read metadata if available
                meta_path = d / ".voxhelm.json"
                meta = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                    except Exception:
                        pass

                heads.append({
                    "name": d.name,
                    "mode": mode,
                    "visemes": asset_count,
                    "complete": asset_count >= 15,
                    "style": meta.get("style", ""),
                })
        return heads

    @app.get("/api/presets")
    async def list_presets():
        return [{"key": k, "description": v} for k, v in PRESETS.items()]

    @app.post("/api/generate-base")
    async def generate_base(req: GenerateBaseRequest):
        if req.preset and req.preset in PRESETS:
            style = PRESETS[req.preset]
            name = req.name or req.preset
        elif req.style:
            style = req.style
            name = req.name or re.sub(r"[^a-z0-9]+", "_", style[:40].lower()).strip("_")
        else:
            raise HTTPException(400, "Provide style or preset")

        # Save metadata
        head_dir = HEADS_DIR / name
        head_dir.mkdir(parents=True, exist_ok=True)
        meta = {"mode": req.mode, "style": style, "name": name, "model": req.model}
        (head_dir / ".voxhelm.json").write_text(json.dumps(meta, indent=2))

        try:
            if req.mode == "svg":
                result = svg_gen.generate_base(
                    style=style, name=name, model=req.model, out_root=HEADS_DIR,
                )
            else:
                result = photo_gen.generate_base(
                    style=style, name=name, out_root=HEADS_DIR,
                )
            return {"name": name, "base": str(result), "ok": True}
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/generate-visemes")
    async def generate_visemes(req: GenerateVisemesRequest):
        head_dir = HEADS_DIR / req.head
        meta_path = head_dir / ".voxhelm.json"
        if not meta_path.exists():
            raise HTTPException(404, "Head not found or missing metadata")

        meta = json.loads(meta_path.read_text())

        try:
            if meta["mode"] == "svg":
                gallery = svg_gen.generate_visemes(
                    style=meta["style"], name=req.head,
                    model=meta.get("model", "claude-opus-4-6"),
                    out_root=HEADS_DIR,
                )
            else:
                gallery = photo_gen.generate_visemes(
                    style=meta["style"], name=req.head,
                    out_root=HEADS_DIR,
                )
            return {"name": req.head, "gallery": f"/heads/{req.head}/gallery.html", "ok": True}
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.get("/api/head/{name}/assets")
    async def get_head_assets(name: str):
        head_dir = HEADS_DIR / name
        if not head_dir.exists():
            raise HTTPException(404, "Head not found")

        # Try SVGs first, then PNGs
        assets = {}
        for v in ALL_VISEMES:
            svg_f = head_dir / f"{v}.svg"
            png_f = head_dir / f"{v}.png"
            if svg_f.exists():
                assets[v] = {"type": "svg", "data": svg_f.read_text()}
            elif png_f.exists():
                b64 = base64.b64encode(png_f.read_bytes()).decode()
                assets[v] = {"type": "png", "data": f"data:image/png;base64,{b64}"}
        return assets

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
        if file.endswith(".svg"):
            media = "image/svg+xml"
        elif file.endswith(".png"):
            media = "image/png"
        else:
            media = "text/html"
        return FileResponse(f, media_type=media)

    return app
