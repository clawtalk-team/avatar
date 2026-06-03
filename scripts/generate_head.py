#!/usr/bin/env python3
"""
generate_head.py  —  generate a full set of viseme SVGs for one character
-------------------------------------------------------------------------
Given a style prompt describing a character, generates one SVG per viseme
(15 total) all sharing the same character design.  The first frame (sil)
is used as a reference for every subsequent generation to lock identity.

Usage:
  python scripts/generate_head.py \
    --style "young woman, warm olive skin, dark curly hair, friendly cartoon, flat design" \
    --name "young_woman"

  python scripts/generate_head.py --list-presets   # show bundled presets

Outputs:
  outputs/heads/<name>/sil.svg … outputs/heads/<name>/U.svg
  outputs/heads/<name>/gallery.html
"""

import argparse
import os
import re
import sys
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
    import anthropic
except ImportError:
    sys.exit("anthropic package not found — run: pip install anthropic")

try:
    import openai as _openai_mod
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ── Bundled character presets ─────────────────────────────────────────────────
PRESETS = {
    "young_man":    "young man in his mid-20s, short dark hair, light skin, clean-shaven, bright eyes, friendly cartoon, flat design, warm colours",
    "middle_man":   "middle-aged man in his 40s, salt-and-pepper stubble, medium-brown skin, slight smile lines, professional cartoon, flat design",
    "older_man":    "elderly man in his 70s, white hair, weathered warm skin, kind deep-set eyes, gentle expression, cartoon, flat design",
    "young_woman":  "young woman in her mid-20s, long auburn hair, fair freckled skin, wide expressive eyes, cheerful cartoon, flat design, warm colours",
    "middle_woman": "middle-aged woman in her 40s, shoulder-length dark hair with grey streaks, medium-brown skin, warm smile, cartoon, flat design",
    "older_woman":  "elderly woman in her 70s, silver bun, light wrinkled skin, rosy cheeks, warm grandmotherly expression, cartoon, flat design",
}

# ── Viseme definitions ────────────────────────────────────────────────────────
VISEMES = {
    "sil": {"phonemes": "silence",        "mouth": "closed, lips neutral, relaxed"},
    "PP":  {"phonemes": "p, b, m",        "mouth": "lips firmly pressed together, slight tension"},
    "FF":  {"phonemes": "f, v",           "mouth": "upper teeth lightly resting on lower lip, slight gap"},
    "TH":  {"phonemes": "th, dh",         "mouth": "tongue tip just visible between slightly parted teeth"},
    "DD":  {"phonemes": "t, d",           "mouth": "mouth slightly open, tongue behind upper teeth"},
    "kk":  {"phonemes": "k, g",           "mouth": "mouth open, back of tongue raised, mid-open"},
    "CH":  {"phonemes": "ch, j, sh, zh",  "mouth": "lips rounded and slightly forward, slightly open"},
    "SS":  {"phonemes": "s, z",           "mouth": "lips wide and slightly parted, teeth nearly closed"},
    "nn":  {"phonemes": "n, l, ng",       "mouth": "mouth slightly open, relaxed tongue position"},
    "RR":  {"phonemes": "r",              "mouth": "lips slightly rounded and forward, mouth slightly open"},
    "aa":  {"phonemes": "ah, aa, ae",     "mouth": "wide open, jaw dropped, lips relaxed and wide"},
    "E":   {"phonemes": "eh, ey",         "mouth": "mouth open half-way, lips wide and spread"},
    "I":   {"phonemes": "ih, iy",         "mouth": "mouth barely open, lips wide and tightly spread"},
    "O":   {"phonemes": "oh, ao, ow",     "mouth": "lips rounded into an O shape, mouth open"},
    "U":   {"phonemes": "oo, uw, uh",     "mouth": "lips tightly rounded and forward like a kiss, small opening"},
}

ALL_VISEMES = list(VISEMES.keys())

SYSTEM_PROMPT = """You are an expert SVG illustrator specialising in cartoon character design.
You produce clean, self-contained SVG files (no external assets, no JavaScript).
Your SVGs use a 512×512 viewBox, are expressive and appealing, and use smooth bezier curves.
All elements are within the SVG — no <image> or <use> with external hrefs.
Reply with ONLY the SVG markup — no code fences, no explanation, no extra text.
The SVG must start with <svg and end with </svg>.
"""


def build_prompt(style: str, viseme: str, first_svg: str | None) -> str:
    v = VISEMES[viseme]
    base = f"""Draw a cartoon face in this style: {style}

Character requirements:
- Friendly, appealing cartoon face on a 512×512 canvas
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


def write_gallery(out_dir: Path, visemes: list[str], style: str, name: str) -> Path:
    cards = []
    for v in visemes:
        svg_file = out_dir / f"{v}.svg"
        if not svg_file.exists():
            cards.append(f'<div class="card"><div class="label">{v}</div><p style="color:#f66">missing</p></div>')
            continue
        svg_content = svg_file.read_text()
        phonemes = VISEMES.get(v, {}).get("phonemes", "")
        cards.append(f"""
      <div class="card">
        <div class="label">{v} — {phonemes}</div>
        <div class="svg-wrap">{svg_content}</div>
      </div>""")

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


def generate(style: str, name: str, visemes: list[str], model: str, out_root: Path,
             skip_existing: bool = False) -> Path:
    out_dir = out_root / name
    out_dir.mkdir(parents=True, exist_ok=True)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

    use_openrouter = False
    if anthropic_key:
        client = anthropic.Anthropic(api_key=anthropic_key)
    elif openrouter_key and HAS_OPENAI:
        use_openrouter = True
        import openai
        client = openai.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
        if "/" not in model:
            model = f"anthropic/{model}"
        print(f"Using OpenRouter: {model}")
    else:
        sys.exit("Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY (with openai package).")

    print(f"\n{'='*60}")
    print(f"  Character : {name}")
    print(f"  Style     : {style}")
    print(f"  Visemes   : {len(visemes)}")
    print(f"  Output    : {out_dir}")
    print(f"{'='*60}")

    first_svg = None
    # Pre-load existing sil if skipping
    if skip_existing and (out_dir / "sil.svg").exists():
        first_svg = (out_dir / "sil.svg").read_text()

    for i, viseme in enumerate(visemes):
        if viseme not in VISEMES:
            print(f"  [{viseme}] unknown — skipping")
            continue
        out_file = out_dir / f"{viseme}.svg"
        if skip_existing and out_file.exists():
            print(f"  [{i+1:2d}/{len(visemes)}] {viseme:4s}  SKIP (exists)")
            if first_svg is None:
                first_svg = out_file.read_text()
            continue

        print(f"  [{i+1:2d}/{len(visemes)}] {viseme:4s}  generating...", end=" ", flush=True)
        prompt = build_prompt(style, viseme, first_svg)

        try:
            if use_openrouter:
                response = client.chat.completions.create(
                    model=model, max_tokens=4096,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": prompt}],
                )
                svg_text = response.choices[0].message.content.strip()
                tokens_out = response.usage.completion_tokens
            else:
                message = client.messages.create(
                    model=model, max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                svg_text = message.content[0].text.strip()
                tokens_out = message.usage.output_tokens

            if svg_text.startswith("```"):
                svg_text = re.sub(r"^```[a-z]*\n?", "", svg_text)
                svg_text = re.sub(r"\n?```$", "", svg_text)
                svg_text = svg_text.strip()

            if not svg_text.startswith("<svg"):
                print(f"WARN: unexpected response: {svg_text[:80]}")

            out_file.write_text(svg_text)
            print(f"OK  ({len(svg_text):,} chars, {tokens_out} tok)")

            if first_svg is None:
                first_svg = svg_text

        except Exception as e:
            print(f"FAILED: {e}")

    gallery = write_gallery(out_dir, visemes, style, name)
    return gallery


def main():
    parser = argparse.ArgumentParser(description="Generate cartoon face viseme SVGs via Claude API")
    parser.add_argument("--style", help="Character style description")
    parser.add_argument("--name", help="Output directory name (default: derived from style)")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), help="Use a bundled character preset")
    parser.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    parser.add_argument("--visemes", nargs="+", default=ALL_VISEMES, help="Visemes to generate (default: all 15)")
    parser.add_argument("--model", default="claude-opus-4-6", help="Claude model")
    parser.add_argument("--out", default="outputs/heads", help="Root output directory")
    parser.add_argument("--skip-existing", action="store_true", help="Skip visemes that already have SVG files")
    args = parser.parse_args()

    if args.list_presets:
        print("\nAvailable presets:\n")
        for k, v in PRESETS.items():
            print(f"  --preset {k}")
            print(f"    {v}\n")
        return

    if args.preset:
        style = PRESETS[args.preset]
        name = args.name or args.preset
    elif args.style:
        style = args.style
        name = args.name or re.sub(r"[^a-z0-9]+", "_", style[:40].lower()).strip("_")
    else:
        parser.error("Provide --style or --preset (or --list-presets to see options)")

    out_root = REPO_ROOT / args.out
    gallery = generate(style, name, args.visemes, args.model, out_root,
                       skip_existing=args.skip_existing)
    print(f"\nGallery: {gallery}")

    import subprocess
    subprocess.run(["open", str(gallery)], check=False)


if __name__ == "__main__":
    main()
