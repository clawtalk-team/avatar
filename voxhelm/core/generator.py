"""SVG head generation — produces 15 viseme SVGs for a character."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable

from .api_client import LLMClient, get_llm_client
from .presets import PRESETS
from .visemes import VISEMES, ALL_VISEMES

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert SVG illustrator specialising in cartoon character design.
You produce clean, self-contained SVG files (no external assets, no JavaScript).
Your SVGs use a 512x512 viewBox, are expressive and appealing, and use smooth bezier curves.
All elements are within the SVG — no <image> or <use> with external hrefs.
Reply with ONLY the SVG markup — no code fences, no explanation, no extra text.
The SVG must start with <svg and end with </svg>.
"""


def build_prompt(style: str, viseme: str, first_svg: str | None) -> str:
    """Build the generation prompt for a single viseme frame."""
    v = VISEMES[viseme]
    base = f"""Draw a cartoon face in this style: {style}

Character requirements:
- Friendly, appealing cartoon face on a 512x512 canvas
- Face centered in the canvas with some padding
- Expressive eyes (open, with pupils/irises)
- Eyebrows showing a neutral or slightly happy expression
- Ears visible on the sides
- Simple neck and shoulders at the bottom (optional)
- Clean flat-design aesthetic with smooth curves

Mouth shape for viseme "{viseme}" (phonemes: {v['phonemes']}):
{v['mouth']}

The mouth is the MOST IMPORTANT part — it must clearly show the "{viseme}" shape.
Make the mouth large enough to be clearly readable at small sizes.
"""
    if first_svg:
        base += f"""
CRITICAL: Match the face design from this reference SVG exactly — same head shape, eye style,
colours, hair, skin tone, and overall character. Only the MOUTH shape should differ.

Reference SVG (viseme "sil" — closed mouth):
{first_svg[:3000]}
"""
    else:
        base += """
This is the reference frame (silent/closed mouth). Establish the character design here —
it will be reused for all other visemes.
"""
    return base


def _clean_svg(text: str) -> str:
    """Strip code fences if present."""
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    return text


def write_gallery(out_dir: Path, visemes: list[str], style: str, name: str) -> Path:
    """Write an HTML gallery page for the generated SVGs."""
    cards = []
    for v in visemes:
        svg_file = out_dir / f"{v}.svg"
        if not svg_file.exists():
            cards.append(
                f'<div class="card"><div class="label">{v}</div>'
                f'<p style="color:#f66">missing</p></div>'
            )
            continue
        svg_content = svg_file.read_text()
        phonemes = VISEMES.get(v, {}).get("phonemes", "")
        cards.append(
            f'<div class="card">'
            f'<div class="label">{v} — {phonemes}</div>'
            f'<div class="svg-wrap">{svg_content}</div>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>{name} — Viseme Gallery</title>
<style>
  body{{background:#1a1a1a;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
  h1{{color:#fff;margin-bottom:4px}}
  p.sub{{color:#888;margin-top:0;margin-bottom:20px;font-size:14px}}
  .grid{{display:flex;flex-wrap:wrap;gap:20px}}
  .card{{background:#2a2a2a;border-radius:12px;padding:12px;text-align:center;width:220px}}
  .label{{font-size:12px;color:#aaa;margin:0 0 8px}}
  .svg-wrap svg{{width:200px;height:200px;display:block;margin:0 auto}}
</style></head>
<body>
  <h1>{name}</h1>
  <p class="sub">Style: {style}</p>
  <div class="grid">{"".join(cards)}</div>
</body></html>"""

    gallery = out_dir / "gallery.html"
    gallery.write_text(html)
    return gallery


def generate(
    style: str,
    name: str,
    visemes: list[str] | None = None,
    model: str = "claude-opus-4-6",
    out_root: Path | str = "outputs/heads",
    skip_existing: bool = False,
    on_progress: Callable[[str, int, int, str], None] | None = None,
    client: LLMClient | None = None,
) -> Path:
    """Generate a full set of viseme SVGs for a character.

    Args:
        style: Character style description.
        name: Output directory name.
        visemes: List of viseme keys to generate (default: all 15).
        model: Claude model name.
        out_root: Root output directory.
        skip_existing: Skip visemes that already have SVG files.
        on_progress: Callback(viseme, index, total, status) for progress reporting.
        client: Pre-configured LLM client (created automatically if None).

    Returns:
        Path to the generated gallery HTML file.
    """
    viseme_list = visemes or ALL_VISEMES
    out_dir = Path(out_root) / name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Defer client creation until we actually need to generate something
    _client = client

    log.info("Generating %d visemes for '%s' → %s", len(viseme_list), name, out_dir)

    first_svg = None
    if skip_existing and (out_dir / "sil.svg").exists():
        first_svg = (out_dir / "sil.svg").read_text()

    for i, viseme in enumerate(viseme_list):
        if viseme not in VISEMES:
            log.warning("Unknown viseme '%s' — skipping", viseme)
            continue

        out_file = out_dir / f"{viseme}.svg"
        _log = log.debug if on_progress else log.info
        if skip_existing and out_file.exists():
            _log("[%d/%d] %s SKIP (exists)", i + 1, len(viseme_list), viseme)
            if on_progress:
                on_progress(viseme, i, len(viseme_list), "skip")
            if first_svg is None:
                first_svg = out_file.read_text()
            continue

        _log("[%d/%d] %s generating...", i + 1, len(viseme_list), viseme)
        if on_progress:
            on_progress(viseme, i, len(viseme_list), "generating")

        prompt = build_prompt(style, viseme, first_svg)

        try:
            if _client is None:
                _client = get_llm_client(model)
            resp = _client.generate(SYSTEM_PROMPT, prompt)
            svg_text = _clean_svg(resp.text)

            if not svg_text.startswith("<svg"):
                log.warning("Unexpected response for %s: %s", viseme, svg_text[:80])

            out_file.write_text(svg_text)
            _log("[%d/%d] %s OK (%d chars, %d tok)",
                 i + 1, len(viseme_list), viseme, len(svg_text), resp.output_tokens)

            if on_progress:
                on_progress(viseme, i, len(viseme_list), "ok")

            if first_svg is None:
                first_svg = svg_text

        except Exception as e:
            log.error("[%d/%d] %s FAILED: %s", i + 1, len(viseme_list), viseme, e)
            if on_progress:
                on_progress(viseme, i, len(viseme_list), f"error: {e}")

    gallery = write_gallery(out_dir, viseme_list, style, name)
    return gallery


def load_svgs(svg_dir: Path) -> dict[str, str]:
    """Load all SVG files from a head directory as a {viseme: svg_string} dict."""
    svgs = {}
    for v in ALL_VISEMES:
        f = svg_dir / f"{v}.svg"
        if f.exists():
            content = re.sub(r'<\?xml[^?]*\?>', '', f.read_text()).strip()
            svgs[v] = content
    return svgs
