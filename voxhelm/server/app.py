"""Voxhelm web studio — FastAPI server wrapping core library.

API mirrors the CLI commands:
  GET  /api/presets              — list character presets
  GET  /api/heads                — list generated heads
  POST /api/generate-base        — step 1: generate base frame
  POST /api/generate-visemes     — step 2: generate remaining visemes
  POST /api/generate             — one-shot: base + visemes
  GET  /api/head/{name}/assets   — get all viseme assets
  GET  /api/head/{name}/validate — get validation gallery HTML
  POST /api/speak                — TTS + viseme timeline
"""

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

    app = FastAPI(
        title="Voxhelm Studio",
        description="Avatar generation and audio-driven lip-sync API",
        version="0.2.0",
    )
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

    # ── Request models ─────────────────────────────────────────────────────

    class GenerateBaseRequest(BaseModel):
        mode: str = "svg"
        prompt: Optional[str] = None
        preset: Optional[str] = None
        name: Optional[str] = None
        model: str = "claude-opus-4-6"

    class GenerateVisemesRequest(BaseModel):
        head: str
        skip_existing: bool = True
        include_blink: bool = True

    class GenerateRequest(BaseModel):
        mode: str = "svg"
        prompt: Optional[str] = None
        preset: Optional[str] = None
        name: Optional[str] = None
        model: str = "claude-opus-4-6"
        skip_existing: bool = False
        include_blink: bool = True

    class SpeakRequest(BaseModel):
        head: str
        text: str

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _resolve(req_prompt: str | None, req_preset: str | None, req_name: str | None) -> tuple[str, str]:
        if req_preset and req_preset in PRESETS:
            return PRESETS[req_preset], req_name or req_preset
        elif req_prompt:
            auto = re.sub(r"[^a-z0-9]+", "_", req_prompt[:40].lower()).strip("_")
            return req_prompt, req_name or auto
        else:
            raise HTTPException(400, "Provide prompt or preset")

    def _save_meta(name: str, mode: str, style: str, model: str) -> None:
        head_dir = HEADS_DIR / name
        head_dir.mkdir(parents=True, exist_ok=True)
        meta = {"mode": mode, "style": style, "name": name, "model": model}
        (head_dir / ".voxhelm.json").write_text(json.dumps(meta, indent=2))

    def _load_meta(name: str) -> dict:
        meta_path = HEADS_DIR / name / ".voxhelm.json"
        if not meta_path.exists():
            raise HTTPException(404, f"Head '{name}' not found or missing metadata")
        return json.loads(meta_path.read_text())

    # ── Routes ─────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def root():
        html_file = REPO_ROOT / "webapp" / "index.html"
        if html_file.exists():
            return html_file.read_text()
        return "<h1>Voxhelm Studio</h1><p>See /docs for API reference.</p>"

    @app.get("/api/presets")
    async def list_presets():
        """List available character presets."""
        return [{"key": k, "description": v} for k, v in PRESETS.items()]

    @app.get("/api/heads")
    async def list_heads():
        """List all generated heads with metadata."""
        if not HEADS_DIR.exists():
            return []
        heads = []
        for d in sorted(HEADS_DIR.iterdir()):
            if not d.is_dir():
                continue
            svgs = list(d.glob("*.svg"))
            pngs = [f for f in d.glob("*.png") if f.name != "base.png"]
            mode = "svg" if svgs else "photo" if pngs else "unknown"
            asset_count = len(svgs) if mode == "svg" else len(pngs)

            meta = {}
            meta_path = d / ".voxhelm.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    pass

            heads.append({
                "name": d.name,
                "mode": meta.get("mode", mode),
                "visemes": asset_count,
                "complete": asset_count >= 15,
                "prompt": meta.get("style", ""),
            })
        return heads

    @app.post("/api/generate-base")
    async def generate_base(req: GenerateBaseRequest):
        """Step 1: Generate the base (sil) frame for a character."""
        style, name = _resolve(req.prompt, req.preset, req.name)
        _save_meta(name, req.mode, style, req.model)

        try:
            if req.mode == "svg":
                result = svg_gen.generate_base(
                    style=style, name=name, model=req.model, out_root=HEADS_DIR,
                )
            elif req.mode == "photo":
                result = photo_gen.generate_base(
                    style=style, name=name, out_root=HEADS_DIR,
                )
            else:
                raise HTTPException(400, f"Unknown mode: {req.mode}. Use 'svg' or 'photo'.")

            return {
                "name": name,
                "mode": req.mode,
                "base": str(result),
                "ok": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/generate-visemes")
    async def generate_visemes(req: GenerateVisemesRequest):
        """Step 2: Generate the remaining 14 viseme frames from an approved base."""
        meta = _load_meta(req.head)

        try:
            if meta["mode"] == "svg":
                gallery = svg_gen.generate_visemes(
                    style=meta["style"], name=req.head,
                    model=meta.get("model", "claude-opus-4-6"),
                    out_root=HEADS_DIR, skip_existing=req.skip_existing,
                )
            else:
                gallery = photo_gen.generate_visemes(
                    style=meta["style"], name=req.head,
                    out_root=HEADS_DIR, skip_existing=req.skip_existing,
                    include_blink=req.include_blink,
                )
            return {
                "name": req.head,
                "mode": meta["mode"],
                "gallery": f"/heads/{req.head}/gallery.html",
                "ok": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/generate")
    async def generate(req: GenerateRequest):
        """One-shot: generate base + all visemes in one call."""
        style, name = _resolve(req.prompt, req.preset, req.name)
        _save_meta(name, req.mode, style, req.model)

        try:
            if req.mode == "svg":
                gallery = svg_gen.generate(
                    style=style, name=name, model=req.model,
                    out_root=HEADS_DIR, skip_existing=req.skip_existing,
                )
            elif req.mode == "photo":
                gallery = photo_gen.generate(
                    style=style, name=name,
                    out_root=HEADS_DIR, skip_existing=req.skip_existing,
                    include_blink=req.include_blink,
                )
            else:
                raise HTTPException(400, f"Unknown mode: {req.mode}. Use 'svg' or 'photo'.")

            return {
                "name": name,
                "mode": req.mode,
                "gallery": f"/heads/{name}/gallery.html",
                "ok": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.get("/api/head/{name}/assets")
    async def get_head_assets(name: str):
        """Get all viseme assets for a head (SVG strings or PNG data URIs)."""
        head_dir = HEADS_DIR / name
        if not head_dir.exists():
            raise HTTPException(404, "Head not found")

        meta = {}
        meta_path = head_dir / ".voxhelm.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                pass

        assets = {}
        for v in ALL_VISEMES:
            svg_f = head_dir / f"{v}.svg"
            png_f = head_dir / f"{v}.png"
            if svg_f.exists():
                assets[v] = {"type": "svg", "data": svg_f.read_text()}
            elif png_f.exists():
                b64 = base64.b64encode(png_f.read_bytes()).decode()
                assets[v] = {"type": "png", "data": f"data:image/png;base64,{b64}"}

        # Include extra animation frames (blink, brows_up, etc.)
        extras = {}
        for extra_name in ["blink", "brows_up"]:
            png_f = head_dir / f"{extra_name}.png"
            if png_f.exists():
                b64 = base64.b64encode(png_f.read_bytes()).decode()
                extras[extra_name] = {"type": "png", "data": f"data:image/png;base64,{b64}"}

        return {
            "name": name,
            "mode": meta.get("mode", "svg" if any(
                (head_dir / f"{v}.svg").exists() for v in ALL_VISEMES
            ) else "photo"),
            "prompt": meta.get("style", ""),
            "visemes": len(assets),
            "complete": len(assets) >= 15,
            "assets": assets,
            "extras": extras,
        }

    @app.get("/api/head/{name}/validate", response_class=HTMLResponse)
    async def validate_head(name: str):
        """Get an HTML validation gallery for a head's assets."""
        head_dir = HEADS_DIR / name
        if not head_dir.exists():
            raise HTTPException(404, "Head not found")

        gallery = head_dir / "gallery.html"
        if gallery.exists():
            return gallery.read_text()

        raise HTTPException(404, "Gallery not found. Generate visemes first.")

    @app.post("/api/speak")
    async def speak(req: SpeakRequest):
        """Generate TTS audio with viseme timeline for a head."""
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            raise HTTPException(500, "DEEPGRAM_API_KEY not set")

        head_dir = HEADS_DIR / req.head
        if not head_dir.exists():
            raise HTTPException(404, f"Head '{req.head}' not found")

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
        return {
            "head": req.head,
            "text": req.text,
            "audio_b64": audio_b64,
            "timeline": timeline,
        }

    @app.get("/heads/{name}/{file}")
    async def serve_head_file(name: str, file: str):
        """Serve a raw file from a head directory."""
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
