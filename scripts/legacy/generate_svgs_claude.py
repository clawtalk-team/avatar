#!/usr/bin/env python3
"""
generate_svgs_claude.py  —  prompt-driven cartoon face SVGs via Claude API
--------------------------------------------------------------------------
Uses claude-opus-4-6 to generate one SVG per viseme, all sharing the same
character design, each with the correct mouth shape for that phoneme.

Usage:
  python scripts/generate_svgs_claude.py \
    --style "friendly cartoon robot, flat design, teal and white" \
    --visemes sil PP aa O U I FF CH

The script generates SVGs sequentially and writes a gallery.html.
"""

import argparse
import os
import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Load .env
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
    print("anthropic package not found. Install with: pip install anthropic")
    sys.exit(1)

try:
    import openai as _openai_mod
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ─── Viseme definitions ───────────────────────────────────────────────────────

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

DEFAULT_VISEMES = ["sil", "PP", "aa", "O", "U", "I", "FF", "CH"]

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert SVG illustrator specialising in cartoon character design.
You produce clean, self-contained SVG files (no external assets, no JavaScript).
Your SVGs use a 512×512 viewBox, are expressive and appealing, and use smooth bezier curves.
All elements are within the SVG — no <image> or <use> with external hrefs.
Reply with ONLY the SVG markup — no code fences, no explanation, no extra text.
The SVG must start with <svg and end with </svg>.
"""

# ─── Per-viseme prompt ────────────────────────────────────────────────────────

def build_prompt(style: str, viseme: str, first_svg: str | None) -> str:
    v = VISEMES[viseme]
    phonemes = v["phonemes"]
    mouth_desc = v["mouth"]

    base = f"""Draw a cartoon face in this style: {style}

Character requirements:
- Friendly, appealing cartoon face on a 512×512 canvas
- Face centered in the canvas with some padding
- Expressive eyes (open, with pupils/irises)
- Eyebrows showing a neutral or slightly happy expression
- Ears visible on the sides
- Simple neck and shoulders at the bottom (optional)
- Clean flat-design aesthetic with smooth curves

Mouth shape for viseme "{viseme}" (phonemes: {phonemes}):
{mouth_desc}

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


# ─── Gallery ──────────────────────────────────────────────────────────────────

def write_gallery(out_dir: Path, visemes: list[str], style: str):
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
<head><meta charset="utf-8"/><title>Claude SVG Visemes</title>
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
  <h1>Claude SVG Viseme Faces</h1>
  <p class="sub">Style: {style}</p>
  <div class="grid">{"".join(cards)}</div>
</body></html>"""

    gallery = out_dir / "gallery.html"
    gallery.write_text(html)
    return gallery


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate cartoon face SVGs per viseme via Claude API")
    parser.add_argument("--style", default="friendly cartoon character, flat design, warm colours, expressive",
                        help="Style description for the character")
    parser.add_argument("--visemes", nargs="+", default=DEFAULT_VISEMES,
                        help="Viseme names to generate (default: 8 core visemes)")
    parser.add_argument("--model", default="claude-opus-4-6",
                        help="Claude model to use")
    parser.add_argument("--out", default="outputs/svg_claude",
                        help="Output directory")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

    use_openrouter = False
    if anthropic_key:
        client = anthropic.Anthropic(api_key=anthropic_key)
    elif openrouter_key and HAS_OPENAI:
        use_openrouter = True
        import openai
        client = openai.OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
        # Map model name to OpenRouter format
        if "/" not in args.model:
            args.model = f"anthropic/{args.model}"
        print(f"Using OpenRouter with model: {args.model}")
    else:
        print("Neither ANTHROPIC_API_KEY nor OPENROUTER_API_KEY (with openai package) found.")
        sys.exit(1)

    print(f"Style: {args.style}")
    print(f"Visemes: {args.visemes}")
    print(f"Model: {args.model}")
    print(f"Output: {out_dir}")
    print()

    first_svg = None

    for i, viseme in enumerate(args.visemes):
        if viseme not in VISEMES:
            print(f"[{viseme}] unknown — skipping")
            continue

        out_file = out_dir / f"{viseme}.svg"
        print(f"[{i+1}/{len(args.visemes)}] Generating {viseme}...", end=" ", flush=True)

        prompt = build_prompt(args.style, viseme, first_svg)

        try:
            if use_openrouter:
                response = client.chat.completions.create(
                    model=args.model,
                    max_tokens=4096,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                svg_text = response.choices[0].message.content.strip()
                tokens_out = response.usage.completion_tokens
            else:
                message = client.messages.create(
                    model=args.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                svg_text = message.content[0].text.strip()
                tokens_out = message.usage.output_tokens

            # Strip code fences if present
            if svg_text.startswith("```"):
                svg_text = re.sub(r"^```[a-z]*\n?", "", svg_text)
                svg_text = re.sub(r"\n?```$", "", svg_text)
                svg_text = svg_text.strip()

            if not svg_text.startswith("<svg"):
                print(f"WARN: response doesn't start with <svg, got: {svg_text[:80]}")

            out_file.write_text(svg_text)
            size = len(svg_text)
            print(f"OK ({size:,} chars, {tokens_out} tokens)")

            if first_svg is None:
                first_svg = svg_text

        except Exception as e:
            print(f"FAILED: {e}")

    print()
    gallery = write_gallery(out_dir, args.visemes, args.style)
    import subprocess
    subprocess.run(["open", str(gallery)], check=False)
    print(f"Gallery: {gallery}")


if __name__ == "__main__":
    main()
