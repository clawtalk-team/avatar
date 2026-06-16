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


def generate_base(
    style: str,
    name: str,
    model: str = "claude-opus-4-6",
    out_root: Path | str = "outputs/heads",
    on_progress: Callable[[str, int, int, str], None] | None = None,
    client: LLMClient | None = None,
) -> Path:
    """Generate the base (sil) SVG frame for a character.

    This is step 1 of the workflow: generate base → review → generate visemes.

    Returns:
        Path to the generated sil.svg file.
    """
    out_dir = Path(out_root) / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sil.svg"

    log.info("Generating base SVG for '%s' → %s", name, out_dir)
    if on_progress:
        on_progress("sil", 0, 1, "generating")

    _client = client or get_llm_client(model)
    prompt = build_prompt(style, "sil", None)
    resp = _client.generate(SYSTEM_PROMPT, prompt)
    svg_text = _clean_svg(resp.text)

    if not svg_text.startswith("<svg"):
        log.warning("Unexpected response for sil: %s", svg_text[:80])

    out_file.write_text(svg_text)
    log.info("Base SVG saved (%d chars, %d tok)", len(svg_text), resp.output_tokens)

    if on_progress:
        on_progress("sil", 0, 1, "ok")

    # Write a single-item gallery for review
    write_gallery(out_dir, ["sil"], style, name)
    return out_file


def generate_visemes(
    style: str,
    name: str,
    visemes: list[str] | None = None,
    model: str = "claude-opus-4-6",
    out_root: Path | str = "outputs/heads",
    skip_existing: bool = True,
    on_progress: Callable[[str, int, int, str], None] | None = None,
    client: LLMClient | None = None,
) -> Path:
    """Generate the remaining viseme SVGs using an existing base (sil) as reference.

    This is step 2 of the workflow: generate base → review → generate visemes.
    Requires sil.svg to already exist in the output directory.

    Returns:
        Path to the generated gallery HTML file.
    """
    viseme_list = visemes or ALL_VISEMES
    out_dir = Path(out_root) / name
    sil_path = out_dir / "sil.svg"

    if not sil_path.exists():
        raise FileNotFoundError(
            f"Base SVG not found at {sil_path}. "
            "Run 'voxhelm generate-base' first."
        )

    first_svg = sil_path.read_text()
    _client = client
    remaining = [v for v in viseme_list if v != "sil"]

    log.info("Generating %d visemes for '%s' → %s", len(remaining), name, out_dir)

    for i, viseme in enumerate(remaining):
        if viseme not in VISEMES:
            log.warning("Unknown viseme '%s' — skipping", viseme)
            continue

        out_file = out_dir / f"{viseme}.svg"
        if skip_existing and out_file.exists():
            log.debug("[%d/%d] %s SKIP (exists)", i + 1, len(remaining), viseme)
            if on_progress:
                on_progress(viseme, i, len(remaining), "skip")
            continue

        if on_progress:
            on_progress(viseme, i, len(remaining), "generating")

        prompt = build_prompt(style, viseme, first_svg)

        try:
            if _client is None:
                _client = get_llm_client(model)
            resp = _client.generate(SYSTEM_PROMPT, prompt)
            svg_text = _clean_svg(resp.text)

            if not svg_text.startswith("<svg"):
                log.warning("Unexpected response for %s: %s", viseme, svg_text[:80])

            out_file.write_text(svg_text)
            log.info("[%d/%d] %s OK (%d chars, %d tok)",
                     i + 1, len(remaining), viseme, len(svg_text), resp.output_tokens)

            if on_progress:
                on_progress(viseme, i, len(remaining), "ok")

        except Exception as e:
            log.error("[%d/%d] %s FAILED: %s", i + 1, len(remaining), viseme, e)
            if on_progress:
                on_progress(viseme, i, len(remaining), f"error: {e}")

    gallery = write_gallery(out_dir, viseme_list, style, name)
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
    """Generate a full set of viseme SVGs in one shot (base + visemes).

    For the split workflow, use generate_base() then generate_visemes() instead.
    """
    out_dir = Path(out_root) / name
    sil_path = out_dir / "sil.svg"

    if not (skip_existing and sil_path.exists()):
        generate_base(
            style=style, name=name, model=model, out_root=out_root,
            on_progress=on_progress, client=client,
        )

    return generate_visemes(
        style=style, name=name, visemes=visemes, model=model,
        out_root=out_root, skip_existing=skip_existing,
        on_progress=on_progress, client=client,
    )


def load_svgs(svg_dir: Path) -> dict[str, str]:
    """Load all SVG files from a head directory as a {viseme: svg_string} dict."""
    svgs = {}
    for v in ALL_VISEMES:
        f = svg_dir / f"{v}.svg"
        if f.exists():
            content = re.sub(r'<\?xml[^?]*\?>', '', f.read_text()).strip()
            svgs[v] = content
    return svgs
