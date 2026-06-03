#!/usr/bin/env python3
"""
generate_heads_batch.py  —  generate all 6 preset character heads and build a combined gallery
----------------------------------------------------------------------------------------------
Generates young/middle/older male and female cartoon heads, each with the full 15-viseme set.
Writes individual galleries per head plus a combined showcase gallery.

Usage:
  python scripts/generate_heads_batch.py
  python scripts/generate_heads_batch.py --skip-existing   # resume interrupted run
  python scripts/generate_heads_batch.py --presets young_man young_woman  # subset
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location("generate_head", Path(__file__).parent / "generate_head.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PRESETS = mod.PRESETS
VISEMES = mod.VISEMES
ALL_VISEMES = mod.ALL_VISEMES


def write_showcase(out_root: Path, presets: list[str]) -> Path:
    """Single HTML page showing the sil frame for each head with a link to its gallery."""
    cards = []
    for name in presets:
        head_dir = out_root / name
        sil = head_dir / "sil.svg"
        gallery_link = f"{name}/gallery.html"
        label = name.replace("_", " ").title()
        if sil.exists():
            svg = sil.read_text()
            cards.append(f"""
  <div class="card">
    <a href="{gallery_link}" title="View all visemes">
      <div class="face">{svg}</div>
    </a>
    <div class="name">{label}</div>
    <a class="gallery-link" href="{gallery_link}">View all visemes →</a>
  </div>""")
        else:
            cards.append(f'<div class="card"><div class="name">{label}</div><p style="color:#f66">not generated</p></div>')

    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>ClaWTalk — Head Gallery</title>
<style>
  body{background:#111;color:#eee;font-family:system-ui,sans-serif;padding:32px;display:flex;flex-direction:column;align-items:center;gap:24px}
  h1{font-size:24px;color:#fff;margin:0}
  p.sub{color:#555;font-size:13px;margin:0}
  .row{display:flex;gap:24px;flex-wrap:wrap;justify-content:center}
  .section-title{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#444;width:100%;text-align:center;padding-top:8px}
  .card{background:#1e1e1e;border-radius:14px;padding:16px;text-align:center;width:200px;border:1px solid #2a2a2a}
  .card a{text-decoration:none}
  .face svg{width:168px;height:168px;display:block;margin:0 auto;border-radius:8px;overflow:hidden}
  .name{font-size:14px;font-weight:600;color:#ccc;margin:10px 0 6px}
  .gallery-link{font-size:11px;color:#4a9;text-decoration:none}
  .gallery-link:hover{text-decoration:underline}
</style>
</head>
<body>
<h1>ClaWTalk — Character Head Gallery</h1>
<p class="sub">Claude-generated cartoon heads · 15 visemes each · click a face to see all mouth shapes</p>

<div class="section-title">Male characters</div>
<div class="row">
""" + "".join(c for c in cards if any(k in cards[cards.index(c)] for k in ["young_man", "middle_man", "older_man"])) + """
</div>

<div class="section-title">Female characters</div>
<div class="row">
""" + "".join(c for c in cards if any(k in cards[cards.index(c)] for k in ["young_woman", "middle_woman", "older_woman"])) + """
</div>
</body></html>"""

    # Simpler approach: just dump all cards in order
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>ClaWTalk — Head Gallery</title>
<style>
  body{{background:#111;color:#eee;font-family:system-ui,sans-serif;padding:32px;display:flex;flex-direction:column;align-items:center;gap:24px}}
  h1{{font-size:24px;color:#fff;margin:0}}
  p.sub{{color:#555;font-size:13px;margin:0}}
  .section{{width:100%;max-width:800px}}
  .section-title{{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#555;margin-bottom:16px;border-bottom:1px solid #222;padding-bottom:8px}}
  .row{{display:flex;gap:20px;flex-wrap:wrap}}
  .card{{background:#1e1e1e;border-radius:14px;padding:16px;text-align:center;width:190px;border:1px solid #2a2a2a}}
  .card a{{text-decoration:none}}
  .face svg{{width:158px;height:158px;display:block;margin:0 auto;border-radius:8px}}
  .name{{font-size:13px;font-weight:600;color:#ccc;margin:10px 0 4px}}
  .gallery-link{{font-size:11px;color:#4a9;text-decoration:none}}
  .gallery-link:hover{{text-decoration:underline}}
</style>
</head>
<body>
<h1>ClaWTalk — Character Head Gallery</h1>
<p class="sub">Claude-generated cartoon heads · 15 visemes each · click a face to see all mouth shapes</p>

<div class="section">
  <div class="section-title">Male characters — young · middle-aged · elderly</div>
  <div class="row">{"".join(cards[:3])}</div>
</div>

<div class="section">
  <div class="section-title">Female characters — young · middle-aged · elderly</div>
  <div class="row">{"".join(cards[3:])}</div>
</div>
</body></html>"""

    showcase = out_root / "showcase.html"
    showcase.write_text(html)
    return showcase


def main():
    parser = argparse.ArgumentParser(description="Batch-generate all 6 preset character heads")
    parser.add_argument("--presets", nargs="+", default=list(PRESETS.keys()),
                        choices=list(PRESETS.keys()), help="Subset of presets to generate")
    parser.add_argument("--visemes", nargs="+", default=ALL_VISEMES, help="Visemes to generate")
    parser.add_argument("--model", default="claude-opus-4-6")
    parser.add_argument("--out", default="outputs/heads")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    out_root = REPO_ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"Generating {len(args.presets)} character heads × {len(args.visemes)} visemes each")
    print(f"Output: {out_root}\n")

    for preset in args.presets:
        style = PRESETS[preset]
        gallery = mod.generate(
            style=style, name=preset, visemes=args.visemes,
            model=args.model, out_root=out_root,
            skip_existing=args.skip_existing,
        )
        print(f"  → {gallery.relative_to(REPO_ROOT)}")

    showcase = write_showcase(out_root, args.presets)
    print(f"\nShowcase: {showcase}")
    subprocess.run(["open", str(showcase)], check=False)


if __name__ == "__main__":
    main()
