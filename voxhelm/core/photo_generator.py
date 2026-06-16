"""Photorealistic head generation — produces 15 viseme PNGs via Gemini Flash Image.

Strategy (identity lock):
  1. Generate ONE base portrait (mouth closed, neutral) — text-to-image.
  2. For each of the 15 OVR visemes, EDIT the base portrait so that only the
     mouth/jaw changes to the target shape.
  3. Optionally generate a blink frame (eyes closed).

Uses Gemini 2.5 Flash Image via OpenRouter (no third-party HTTP deps — urllib only).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable

from .visemes import ALL_VISEMES

log = logging.getLogger(__name__)

MODEL = "google/gemini-2.5-flash-image"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Natural-language mouth shape per viseme.
VISEME_MOUTHS: dict[str, str] = {
    "sil": "lips gently closed and relaxed, mouth at rest",
    "PP":  "lips pressed firmly together, as when making a 'p' or 'b' sound",
    "FF":  "the lower lip tucked lightly under the upper front teeth, as when making an 'f' or 'v' sound",
    "TH":  "mouth slightly open with the tongue tip just visible between the teeth, as when making a 'th' sound",
    "DD":  "mouth slightly open, tongue tip raised behind the upper teeth, as when making a 't' or 'd' sound",
    "kk":  "mouth slightly open in a relaxed neutral position, as when making a 'k' or 'g' sound",
    "CH":  "lips slightly rounded and pushed forward with a small opening, as when making a 'ch' or 'sh' sound",
    "SS":  "teeth nearly together, lips spread wide with a narrow opening, as when making an 's' or 'z' sound",
    "nn":  "mouth slightly open, tongue tip touching behind the upper teeth, as when making an 'n' or 'l' sound",
    "RR":  "lips slightly rounded and a little forward, as when making an 'r' sound",
    "aa":  "mouth open a moderate amount in a natural relaxed speaking position, as when saying 'ah' mid-sentence",
    "E":   "mouth open a small amount with lips slightly spread, as when saying 'eh' in normal conversation",
    "I":   "lips spread wide in a slight smile with a small opening, as when saying 'ee'",
    "O":   "lips rounded into a clear 'O' shape, moderately open, as when saying 'oh'",
    "U":   "lips tightly rounded and pushed forward with a small opening, as when saying 'oo'",
}

# Extra non-viseme edits.
EXTRA_EDITS: dict[str, tuple[str, str]] = {
    "blink": ("eyes",
              "both eyes fully closed with the eyelids gently shut, as in the middle of a "
              "natural blink — relaxed lids, not squeezed"),
}


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    raise RuntimeError("OPENROUTER_API_KEY not set")


def _post(payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/clawtalk/photo-generation",
            "X-Title": "voxhelm-photo",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_image(resp: dict) -> bytes:
    """Pull the base64 PNG out of the OpenRouter response."""
    msg = resp["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        raise RuntimeError(f"No image in response: {json.dumps(resp)[:400]}")
    url = images[0]["image_url"]["url"]
    if not url.startswith("data:"):
        raise RuntimeError(f"Unexpected image url (not a data URL): {url[:80]}")
    b64 = url.split(",", 1)[1]
    return base64.b64decode(b64)


def _generate_image(prompt: str, api_key: str, input_png: bytes | None = None) -> bytes:
    """Call Gemini Flash Image via OpenRouter with retry."""
    content: list = [{"type": "text", "text": prompt}]
    if input_png is not None:
        b64 = base64.b64encode(input_png).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }
    last_err = None
    for attempt in range(1, 4):
        try:
            return _extract_image(_post(payload, api_key))
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, KeyError) as e:
            last_err = e
            detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    detail = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
            log.warning("Attempt %d failed: %s %s", attempt, e, detail)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Image generation failed after retries: {last_err}")


def _build_base_prompt(style: str) -> str:
    return (
        f"A photorealistic head-and-shoulders studio portrait of {style}. "
        "Neutral relaxed expression, lips gently closed, facing the camera directly, "
        "head perfectly centered and upright, even soft frontal studio lighting, "
        "plain light-gray seamless background, sharp focus, shot on an 85mm lens. "
        "Square 1:1 framing."
    )


def _build_edit_prompt(style: str, viseme: str) -> str:
    desc = VISEME_MOUTHS[viseme]
    return (
        f"Edit the provided portrait. Keep the EXACT same person as {style} — "
        "identical face shape, hairstyle, skin tone and texture, camera angle, head "
        "position, framing, lighting, and plain gray background. "
        "Keep the eyes and eyebrows exactly as in the base. "
        f"Change ONLY the mouth and jaw so the mouth shows: {desc}. "
        "Keep a calm neutral expression with relaxed eyebrows and normal eyes — "
        "do NOT raise the eyebrows or widen the eyes. "
        "Do not change anything else. Front-facing, looking straight at the camera."
    )


def _build_extra_edit_prompt(style: str, region: str, desc: str) -> str:
    return (
        f"Edit the provided portrait. Keep the EXACT same person as {style} — "
        "identical face shape, hairstyle, skin tone and texture, camera angle, head "
        "position, framing, lighting, and plain gray background. "
        "Keep the mouth exactly as in the base (gently closed). "
        f"Change ONLY the {region} so that: {desc}. "
        "Do not change anything else. Front-facing, looking straight at the camera."
    )


def write_gallery(out_dir: Path, viseme_list: list[str], style: str, name: str) -> Path:
    """Write an HTML gallery page for the generated photo visemes."""
    cards = []
    for v in viseme_list:
        png_file = out_dir / f"{v}.png"
        if not png_file.exists():
            cards.append(
                f'<div class="card"><div class="label">{v}</div>'
                f'<p style="color:#f66">missing</p></div>'
            )
            continue
        # Embed as base64 for a self-contained HTML file
        b64 = base64.b64encode(png_file.read_bytes()).decode()
        mouth_desc = VISEME_MOUTHS.get(v, "")
        cards.append(
            f'<div class="card">'
            f'<div class="label">{v}</div>'
            f'<img src="data:image/png;base64,{b64}" alt="{v}"/>'
            f'<div class="desc">{mouth_desc}</div>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>{name} — Photo Viseme Gallery</title>
<style>
  body{{background:#1a1a1a;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
  h1{{color:#fff;margin-bottom:4px}}
  p.sub{{color:#888;margin-top:0;margin-bottom:20px;font-size:14px}}
  .grid{{display:flex;flex-wrap:wrap;gap:20px}}
  .card{{background:#2a2a2a;border-radius:12px;padding:12px;text-align:center;width:220px}}
  .label{{font-size:14px;font-weight:700;color:#7cf;margin:0 0 8px}}
  .card img{{width:200px;height:200px;display:block;margin:0 auto;border-radius:8px;object-fit:cover}}
  .desc{{font-size:11px;color:#888;margin-top:6px;line-height:1.3}}
</style></head>
<body>
  <h1>{name}</h1>
  <p class="sub">Style: {style} &mdash; Mode: photo</p>
  <div class="grid">{"".join(cards)}</div>
</body></html>"""

    gallery = out_dir / "gallery.html"
    gallery.write_text(html)
    return gallery


def generate_base(
    style: str,
    name: str,
    out_root: Path | str = "outputs/heads",
    on_progress: Callable[[str, int, int, str], None] | None = None,
) -> Path:
    """Generate the base portrait (sil mouth) for a character.

    This is step 1 of the workflow: generate base → review → generate visemes.

    Returns:
        Path to the generated base.png file.
    """
    api_key = _get_api_key()
    out_dir = Path(out_root) / name
    out_dir.mkdir(parents=True, exist_ok=True)

    base_path = out_dir / "base.png"
    sil_path = out_dir / "sil.png"

    log.info("Generating base portrait for '%s' → %s", name, out_dir)
    if on_progress:
        on_progress("base", 0, 1, "generating")

    base_png = _generate_image(_build_base_prompt(style), api_key)
    base_path.write_bytes(base_png)
    sil_path.write_bytes(base_png)  # sil = base portrait
    log.info("Base portrait saved (%d bytes)", len(base_png))

    if on_progress:
        on_progress("base", 0, 1, "ok")

    # Write manifest with just the base
    manifest = {"base": "base.png", "visemes": {"sil": "sil.png"}}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Write a single-item gallery for review
    write_gallery(out_dir, ["sil"], style, name)
    return base_path


def generate_visemes(
    style: str,
    name: str,
    visemes: list[str] | None = None,
    out_root: Path | str = "outputs/heads",
    skip_existing: bool = True,
    include_blink: bool = True,
    on_progress: Callable[[str, int, int, str], None] | None = None,
) -> Path:
    """Generate the remaining viseme PNGs using an existing base portrait.

    This is step 2 of the workflow: generate base → review → generate visemes.
    Requires base.png to already exist in the output directory.

    Returns:
        Path to the generated gallery HTML file.
    """
    api_key = _get_api_key()
    viseme_list = visemes or ALL_VISEMES
    out_dir = Path(out_root) / name
    base_path = out_dir / "base.png"

    if not base_path.exists():
        raise FileNotFoundError(
            f"Base portrait not found at {base_path}. "
            "Run 'voxhelm generate-base' first."
        )

    base_png = base_path.read_bytes()
    remaining = [v for v in viseme_list if v != "sil"]
    total = len(remaining) + (1 if include_blink else 0)

    log.info("Generating %d photo visemes for '%s' → %s", total, name, out_dir)

    # Load or create manifest
    man_path = out_dir / "manifest.json"
    if man_path.exists():
        manifest = json.loads(man_path.read_text())
    else:
        manifest = {"base": "base.png", "visemes": {"sil": "sil.png"}}

    for i, viseme in enumerate(remaining):
        if viseme not in VISEME_MOUTHS:
            log.warning("Unknown viseme '%s' — skipping", viseme)
            continue

        out_file = out_dir / f"{viseme}.png"
        if skip_existing and out_file.exists():
            log.debug("[%d/%d] %s SKIP (exists)", i + 1, total, viseme)
            if on_progress:
                on_progress(viseme, i, total, "skip")
            manifest["visemes"][viseme] = f"{viseme}.png"
            continue

        if on_progress:
            on_progress(viseme, i, total, "generating")

        try:
            prompt = _build_edit_prompt(style, viseme)
            png = _generate_image(prompt, api_key, input_png=base_png)
            out_file.write_bytes(png)
            manifest["visemes"][viseme] = f"{viseme}.png"
            log.info("[%d/%d] %s OK (%d bytes)", i + 1, total, viseme, len(png))
            if on_progress:
                on_progress(viseme, i, total, "ok")
        except Exception as e:
            log.error("[%d/%d] %s FAILED: %s", i + 1, total, viseme, e)
            if on_progress:
                on_progress(viseme, i, total, f"error: {e}")

    # Blink frame
    if include_blink:
        blink_path = out_dir / "blink.png"
        if not (skip_existing and blink_path.exists()):
            idx = len(remaining)
            if on_progress:
                on_progress("blink", idx, total, "generating")
            try:
                region, desc = EXTRA_EDITS["blink"]
                prompt = _build_extra_edit_prompt(style, region, desc)
                png = _generate_image(prompt, api_key, input_png=base_png)
                blink_path.write_bytes(png)
                log.info("Blink frame saved (%d bytes)", len(png))
                if on_progress:
                    on_progress("blink", idx, total, "ok")
            except Exception as e:
                log.error("Blink FAILED: %s", e)
                if on_progress:
                    on_progress("blink", idx, total, f"error: {e}")

    # Write manifest
    man_path.write_text(json.dumps(manifest, indent=2))

    gallery = write_gallery(out_dir, viseme_list, style, name)
    return gallery


def generate(
    style: str,
    name: str,
    visemes: list[str] | None = None,
    out_root: Path | str = "outputs/heads",
    skip_existing: bool = False,
    include_blink: bool = True,
    on_progress: Callable[[str, int, int, str], None] | None = None,
) -> Path:
    """Generate a full set of photo visemes in one shot (base + visemes).

    For the split workflow, use generate_base() then generate_visemes() instead.
    """
    out_dir = Path(out_root) / name
    base_path = out_dir / "base.png"

    if not (skip_existing and base_path.exists()):
        generate_base(
            style=style, name=name, out_root=out_root,
            on_progress=on_progress,
        )

    return generate_visemes(
        style=style, name=name, visemes=visemes, out_root=out_root,
        skip_existing=skip_existing, include_blink=include_blink,
        on_progress=on_progress,
    )


def load_pngs(png_dir: Path) -> dict[str, bytes]:
    """Load all PNG files from a head directory as a {viseme: bytes} dict."""
    pngs = {}
    for v in ALL_VISEMES:
        f = png_dir / f"{v}.png"
        if f.exists():
            pngs[v] = f.read_bytes()
    return pngs
