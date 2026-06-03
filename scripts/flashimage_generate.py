#!/usr/bin/env python3
"""
Generate photorealistic viseme stills with Gemini 2.5 Flash Image (nano-banana)
via OpenRouter.

Strategy (identity lock):
  1. Generate ONE base portrait (mouth closed, neutral) — text-to-image.
  2. For each of the 15 OVR visemes, EDIT the base portrait so that only the
     mouth/jaw changes to the target shape. Passing the base image as input and
     instructing "same person, only the mouth changes" keeps identity stable
     across all frames — the lesson learned from the failed SD-inpainting run.

Output:
  outputs/flashimage/base.png
  outputs/flashimage/<viseme>.png   (15 files)
  outputs/flashimage/manifest.json  (viseme -> filename, for the browser demo)

No third-party deps (urllib only) so it runs under the project's Python 3.14
venv which has no packages installed.

Usage:
  python scripts/flashimage_generate.py            # all visemes
  python scripts/flashimage_generate.py sil aa O   # subset (de-risk run)
  python scripts/flashimage_generate.py --base-only
"""

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "flashimage"
MODEL = "google/gemini-2.5-flash-image"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Identity description reused in every prompt so the model re-anchors the same
# person even when it does not perfectly preserve input pixels.
CHARACTER = (
    "a friendly woman in her early 30s with shoulder-length dark brown hair, "
    "warm light-olive skin, brown eyes, subtle natural makeup"
)

BASE_PROMPT = (
    f"A photorealistic head-and-shoulders studio portrait of {CHARACTER}. "
    "Neutral relaxed expression, lips gently closed, facing the camera directly, "
    "head perfectly centered and upright, even soft frontal studio lighting, "
    "plain light-gray seamless background, sharp focus, shot on an 85mm lens. "
    "Square 1:1 framing."
)

# Natural-language mouth shape per viseme (mapped from the (jaw,spread,part) table).
VISEME_MOUTHS = {
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
    "aa":  "mouth open a moderate amount in a natural relaxed speaking position, as when saying 'ah' mid-sentence — NOT a wide surprised or laughing open",
    "E":   "mouth open a small amount with lips slightly spread, as when saying 'eh' in normal conversation",
    "I":   "lips spread wide in a slight smile with a small opening, as when saying 'ee'",
    "O":   "lips rounded into a clear 'O' shape, moderately open, as when saying 'oh'",
    "U":   "lips tightly rounded and pushed forward with a small opening, as when saying 'oo'",
}

VISEME_ORDER = list(VISEME_MOUTHS.keys())

# Non-viseme edits (idle motion). Same identity-lock trick, different region.
EXTRA_EDITS = {
    "blink": ("eyes",
              "both eyes fully closed with the eyelids gently shut, as in the middle of a "
              "natural blink — relaxed lids, not squeezed"),
}


def load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("ERROR: OPENROUTER_API_KEY not found in env or .env")


def post(payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/clawtalk/photo-generation",
            "X-Title": "viseme-morph-spike",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_image(resp: dict) -> bytes:
    """Pull the base64 PNG out of choices[0].message.images[0].image_url.url."""
    msg = resp["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        raise RuntimeError(f"No image in response: {json.dumps(resp)[:400]}")
    url = images[0]["image_url"]["url"]
    if not url.startswith("data:"):
        raise RuntimeError(f"Unexpected image url (not a data URL): {url[:80]}")
    b64 = url.split(",", 1)[1]
    return base64.b64decode(b64)


def generate(prompt: str, api_key: str, input_png: bytes | None = None) -> bytes:
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
            return extract_image(post(payload, api_key))
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, KeyError) as e:
            last_err = e
            detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    detail = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
            print(f"    attempt {attempt} failed: {e} {detail}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"generate failed after retries: {last_err}")


def main() -> None:
    args = [a for a in sys.argv[1:]]
    base_only = "--base-only" in args
    args = [a for a in args if not a.startswith("--")]
    targets = args if args else VISEME_ORDER

    api_key = load_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_path = OUT_DIR / "base.png"
    if base_path.exists() and not base_only:
        print(f"[base] reusing existing {base_path}")
        base_png = base_path.read_bytes()
    else:
        print("[base] generating base portrait (text-to-image)...")
        base_png = generate(BASE_PROMPT, api_key)
        base_path.write_bytes(base_png)
        print(f"[base] saved {base_path} ({len(base_png)} bytes)")
    if base_only:
        return

    common = (
        f"Edit the provided portrait. Keep the EXACT same person as {CHARACTER} — "
        "identical face shape, hairstyle, skin tone and texture, camera angle, head "
        "position, framing, lighting, and plain gray background. "
    )
    manifest = {"base": "base.png", "visemes": {}}
    for v in targets:
        if v in VISEME_MOUTHS:
            desc = VISEME_MOUTHS[v]
            prompt = (
                common +
                "Keep the eyes and eyebrows exactly as in the base. "
                f"Change ONLY the mouth and jaw so the mouth shows: {desc}. "
                "Keep a calm neutral expression with relaxed eyebrows and normal eyes — "
                "do NOT raise the eyebrows or widen the eyes. "
                "Do not change anything else. Front-facing, looking straight at the camera."
            )
        elif v in EXTRA_EDITS:
            _region, desc = EXTRA_EDITS[v]
            prompt = (
                common +
                "Keep the mouth exactly as in the base (gently closed). "
                f"Change ONLY the {_region} so that: {desc}. "
                "Do not change anything else. Front-facing, looking straight at the camera."
            )
        else:
            print(f"[skip] unknown target '{v}'")
            continue
        out = OUT_DIR / f"{v}.png"
        print(f"[{v}] editing base -> {desc[:48]}...")
        png = generate(prompt, api_key, input_png=base_png)
        out.write_bytes(png)
        manifest["visemes"][v] = f"{v}.png"
        print(f"[{v}] saved {out} ({len(png)} bytes)")

    # Merge into existing manifest if doing a subset run
    man_path = OUT_DIR / "manifest.json"
    if man_path.exists():
        try:
            existing = json.loads(man_path.read_text())
            existing.setdefault("visemes", {}).update(manifest["visemes"])
            existing["base"] = manifest["base"]
            manifest = existing
        except Exception:
            pass
    man_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {man_path}")
    print(f"Generated visemes: {sorted(manifest['visemes'])}")


if __name__ == "__main__":
    main()
