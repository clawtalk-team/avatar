"""SVG head generation — produces 15 viseme SVGs for a character."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .api_client import LLMClient, get_llm_client
from .presets import PRESETS
from .visemes import VISEMES, ALL_VISEMES

log = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = """You are an expert SVG illustrator specialising in cartoon character design.
You produce clean, self-contained SVG files (no external assets, no JavaScript).
Your SVGs use a 512x512 viewBox, are expressive and appealing, and use smooth bezier curves.
All elements are within the SVG — no <image> or <use> with external hrefs.
Reply with ONLY the SVG markup — no code fences, no explanation, no extra text.
The SVG must start with <svg and end with </svg>.
"""

MOUTH_SYSTEM_PROMPT = """You are an expert SVG illustrator. You produce SVG path elements for
cartoon mouth shapes. Reply with ONLY the SVG elements — no code fences, no explanation.
Your output will be inserted inside an existing <g id="mouth"> group in a 512x512 SVG.
Output raw SVG elements (paths, ellipses, etc.) — NOT a complete <svg> document.
"""


def build_base_prompt(style: str) -> str:
    """Build the prompt for generating the structured base SVG."""
    return f"""Draw a cartoon face in this style: {style}

Character requirements:
- Friendly, appealing cartoon face on a 512x512 canvas
- Face centered in the canvas with some padding
- Expressive eyes (open, with pupils/irises)
- Eyebrows showing a neutral or slightly happy expression
- Ears visible on the sides
- Simple neck and shoulders at the bottom (optional)
- Clean flat-design aesthetic with smooth curves
- Mouth: closed, lips neutral, relaxed (this is the silent/resting position)

CRITICAL STRUCTURE — you MUST use these exact group IDs:
- Wrap the entire head/hair/ears/neck in <g id="head">...</g>
- Wrap both eyes (whites, irises, pupils) in <g id="eyes">...</g>
- Wrap both eyebrows in <g id="brows">...</g>
- Wrap the mouth (lips, any teeth/tongue) in <g id="mouth">...</g>

The groups must be in this order: head, eyes, brows, mouth (mouth on top).
The mouth must be clearly readable at small sizes.
Hair MUST overlap and sit on top of the head shape using proper layering.
"""


def build_mouth_prompt(style: str, viseme: str, base_svg: str) -> str:
    """Build the prompt for generating just the mouth paths for a viseme."""
    v = VISEMES[viseme]
    return f"""Here is a cartoon face SVG. I need you to generate ONLY the mouth elements
for the viseme "{viseme}" (phonemes: {v['phonemes']}).

Mouth shape: {v['mouth']}

The output will replace the contents of <g id="mouth"> in this SVG:

{base_svg[:4000]}

Generate ONLY the SVG elements (paths, ellipses, rects, etc.) that go inside <g id="mouth">.
Match the same art style, colours, and stroke widths as the existing mouth.
Do NOT output a complete <svg> tag. Do NOT output the <g id="mouth"> wrapper — just the contents.
The mouth must be positioned correctly relative to the face (same center point as the original mouth).
"""


def build_prompt(style: str, viseme: str, first_svg: str | None) -> str:
    """Legacy: build a full-SVG generation prompt (used by one-shot generate)."""
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


def _clean_fragment(text: str) -> str:
    """Clean an SVG fragment (mouth paths) — strip fences and any wrapping tags."""
    text = _clean_svg(text)
    # Strip any accidental <svg> wrapper
    text = re.sub(r'^<svg[^>]*>', '', text)
    text = re.sub(r'</svg>\s*$', '', text)
    # Strip any accidental <g id="mouth"> wrapper
    text = re.sub(r'^<g[^>]*id=["\']mouth["\'][^>]*>', '', text)
    text = re.sub(r'</g>\s*$', '', text)
    return text.strip()


def _swap_mouth(base_svg: str, new_mouth_content: str) -> str:
    """Replace the <g id="mouth">...</g> content in the base SVG."""
    pattern = r'(<g\s+id=["\']mouth["\'][^>]*>)(.*?)(</g>)'
    replacement = rf'\g<1>{new_mouth_content}\g<3>'
    result, count = re.subn(pattern, replacement, base_svg, count=1, flags=re.DOTALL)
    if count == 0:
        log.warning("Could not find <g id='mouth'> in base SVG — appending mouth before </svg>")
        result = base_svg.replace('</svg>', f'<g id="mouth">{new_mouth_content}</g></svg>')
    return result


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
    """Generate the structured base (sil) SVG frame for a character.

    The base SVG uses named groups (<g id="head">, <g id="eyes">,
    <g id="brows">, <g id="mouth">) so that viseme generation can
    swap just the mouth content without regenerating the entire face.

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
    prompt = build_base_prompt(style)
    resp = _client.generate(BASE_SYSTEM_PROMPT, prompt)
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
    """Generate viseme SVGs by swapping mouth content in the structured base.

    Instead of regenerating the entire face for each viseme, this generates
    only the mouth paths and inserts them into the base SVG. This guarantees
    zero identity drift — head, hair, eyes, ears are the same SVG elements.

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

    base_svg = sil_path.read_text()
    _client = client or get_llm_client(model)
    remaining = [v for v in viseme_list if v != "sil"]

    # Build work items — each generates only mouth fragment
    work: list[tuple[str, Path, str]] = []
    for viseme in remaining:
        if viseme not in VISEMES:
            continue
        out_file = out_dir / f"{viseme}.svg"
        if skip_existing and out_file.exists():
            if on_progress:
                on_progress(viseme, 0, len(remaining), "skip")
            continue
        work.append((viseme, out_file, build_mouth_prompt(style, viseme, base_svg)))

    total = len(work)
    if total == 0:
        log.info("All visemes already exist for '%s', nothing to generate", name)
        return write_gallery(out_dir, viseme_list, style, name)

    log.info("Generating %d mouth shapes for '%s' (parallel) → %s", total, name, out_dir)

    max_workers = min(total, 4)
    completed = 0

    def _do_one(item: tuple[str, Path, str]) -> tuple[str, Path, str | None, int, str | None]:
        label, out_path, prompt = item
        try:
            resp = _client.generate(MOUTH_SYSTEM_PROMPT, prompt)
            mouth_content = _clean_fragment(resp.text)
            # Insert mouth into the base SVG
            full_svg = _swap_mouth(base_svg, mouth_content)
            return (label, out_path, full_svg, resp.output_tokens, None)
        except Exception as e:
            return (label, out_path, None, 0, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_do_one, item): item for item in work}
        for future in as_completed(futures):
            label, out_path, svg_text, tokens, error = future.result()
            completed += 1
            if error:
                log.error("[%d/%d] %s FAILED: %s", completed, total, label, error)
                if on_progress:
                    on_progress(label, completed - 1, total, f"error: {error}")
            else:
                out_path.write_text(svg_text)
                log.info("[%d/%d] %s OK (%d mouth chars, %d tok)",
                         completed, total, label, len(svg_text), tokens)
                if on_progress:
                    on_progress(label, completed - 1, total, "ok")

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
