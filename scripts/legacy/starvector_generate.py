#!/usr/bin/env python3
"""
Generate SVG cartoon faces using StarVector (im2svg).

StarVector takes a raster PNG and traces it into clean SVG path code.
We feed it our parametric SVG faces (rasterized to PNG via cairosvg) and
compare the generated SVG against our hand-crafted analytic geometry.

Usage:
    # From project root, with star-vector venv active:
    python scripts/starvector_generate.py

    # Or with explicit venv:
    star-vector/.venv/bin/python scripts/starvector_generate.py

Outputs:
    outputs/starvector/<viseme>_input.png    Rasterized input
    outputs/starvector/<viseme>_output.svg   StarVector SVG output
    outputs/starvector/gallery.html          Side-by-side comparison
"""

import os
import sys
import time
from pathlib import Path

# Allow importing starvector from the cloned repo
REPO_ROOT = Path(__file__).parent.parent
STARVECTOR_REPO = REPO_ROOT / "star-vector"
sys.path.insert(0, str(STARVECTOR_REPO))

import torch
import cairosvg
from PIL import Image
import io

# huggingface_hub 0.36.x in this venv reads from ~/.huggingface/token, but the
# system CLI writes to ~/.cache/huggingface/token. Bridge the gap by writing
# the token to the legacy location that the older library expects.
_hf_token_new = Path.home() / ".cache" / "huggingface" / "token"
_hf_token_old = Path.home() / ".huggingface" / "token"
if _hf_token_new.exists() and not _hf_token_old.exists():
    _hf_token_old.parent.mkdir(parents=True, exist_ok=True)
    _hf_token_old.write_text(_hf_token_new.read_text())

if _hf_token_new.exists():
    _tok = _hf_token_new.read_text().strip()
    os.environ["HF_TOKEN"] = _tok
    os.environ["HUGGING_FACE_HUB_TOKEN"] = _tok

# Add svg_generator to path
sys.path.insert(0, str(REPO_ROOT))
from svg_generator import build_face_svg, VISEMES

OUT_DIR = REPO_ROOT / "outputs" / "starvector"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Use a focused subset for the initial run — covers the main mouth shape categories
TARGET_VISEMES = ["sil", "PP", "aa", "O", "U", "I", "FF", "CH"]

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
MODEL_ID = "starvector/starvector-1b-im2svg"


def rasterize_svg(svg_str: str, size: int = 256) -> Image.Image:
    """Convert SVG string to PIL Image via cairosvg."""
    png_bytes = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def load_model():
    print(f"Loading StarVector 1B from HuggingFace → {MODEL_ID}")
    print(f"Device: {DEVICE}  (MPS = Apple Silicon GPU)")

    from starvector.model.starvector_arch import StarVectorForCausalLM

    token = os.environ.get("HF_TOKEN")
    model = StarVectorForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        trust_remote_code=True,
        token=token,
    )
    model.to(DEVICE)
    model.eval()
    print("Model loaded.\n")
    return model


def generate_svg(model, image_pil: Image.Image, max_length: int = 4000) -> str:
    """Run im2svg on a PIL image, return raw SVG string."""
    # The model's processor handles resizing and normalising
    processor = model.model.processor
    pixel_values = processor(image_pil, return_tensors="pt")["pixel_values"]
    if pixel_values.dim() == 3:
        pixel_values = pixel_values.unsqueeze(0)  # add batch dim: [3,H,W] → [1,3,H,W]
    pixel_values = pixel_values.to(DEVICE, dtype=torch.float16)

    batch = {"image": pixel_values}
    with torch.no_grad():
        raw_svg = model.generate_im2svg(batch, max_length=max_length)[0]
    return raw_svg


def write_gallery(results: list[dict]):
    """Write a side-by-side HTML gallery comparing input PNG and StarVector SVG."""
    cards = []
    for r in results:
        input_rel = Path(r["input_png"]).relative_to(REPO_ROOT)
        output_rel = Path(r["output_svg"]).relative_to(REPO_ROOT)
        cards.append(f"""
      <div class="card">
        <div class="label">{r['viseme']} — input (rasterized SVG)</div>
        <img src="../{input_rel}" width="256" height="256"/>
        <div class="label">StarVector output</div>
        <object type="image/svg+xml" data="../{output_rel}" width="256" height="256">
          <img src="../{input_rel}" width="256" height="256"/>
        </object>
        <div class="time">{r['elapsed']:.1f}s</div>
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>StarVector — Cartoon Face Gallery</title>
  <style>
    body {{ background:#1a1a1a; color:#eee; font-family:system-ui,sans-serif; padding:20px; }}
    h1   {{ color:#fff; margin-bottom:16px; }}
    .grid {{ display:flex; flex-wrap:wrap; gap:20px; }}
    .card {{ background:#2a2a2a; border-radius:12px; padding:12px; text-align:center; width:270px; }}
    .label {{ font-size:12px; color:#aaa; margin:6px 0 4px; }}
    .time  {{ font-size:11px; color:#666; margin-top:8px; font-family:monospace; }}
  </style>
</head>
<body>
  <h1>StarVector im2svg — Cartoon Viseme Faces</h1>
  <p style="color:#888">Input: parametric SVG rasterized to 256×256 PNG. Output: StarVector 1B trace.</p>
  <div class="grid">{"".join(cards)}
  </div>
</body>
</html>"""

    out = OUT_DIR / "gallery.html"
    out.write_text(html)
    print(f"\nGallery: {out}")
    return out


def main():
    print(f"StarVector SVG face generation")
    print(f"Visemes: {TARGET_VISEMES}")
    print(f"Output: {OUT_DIR}\n")

    model = load_model()
    results = []

    for viseme_name in TARGET_VISEMES:
        if viseme_name not in VISEMES:
            print(f"  [skip] {viseme_name} not in VISEMES dict")
            continue

        jaw, spread, part = VISEMES[viseme_name]["shape"]
        print(f"[{viseme_name:4s}]  jaw={jaw:.2f}  spread={spread:+.2f}  part={part:+.2f}")

        # 1. Generate SVG via our parametric generator
        svg_str = build_face_svg(viseme_name, jaw, spread, part)

        # 2. Rasterize to PNG for StarVector input
        try:
            img = rasterize_svg(svg_str, size=224)
        except Exception as e:
            print(f"  rasterize failed: {e}")
            continue

        input_path = OUT_DIR / f"{viseme_name}_input.png"
        img.save(input_path)
        print(f"  input PNG: {input_path.name}")

        # 3. Run StarVector
        t0 = time.time()
        try:
            raw_svg = generate_svg(model, img)
            elapsed = time.time() - t0
        except Exception as e:
            print(f"  generation failed: {e}")
            continue

        # 4. Save SVG output
        output_path = OUT_DIR / f"{viseme_name}_output.svg"
        output_path.write_text(raw_svg)
        svg_size = len(raw_svg)
        print(f"  output SVG: {output_path.name}  ({svg_size:,} chars, {elapsed:.1f}s)\n")

        results.append({
            "viseme": viseme_name,
            "input_png": str(input_path),
            "output_svg": str(output_path),
            "elapsed": elapsed,
        })

    if results:
        gallery = write_gallery(results)
        import subprocess
        subprocess.run(["open", str(gallery)], check=False)
        print(f"\nDone — {len(results)}/{len(TARGET_VISEMES)} visemes generated.")
    else:
        print("No outputs produced.")


if __name__ == "__main__":
    main()
