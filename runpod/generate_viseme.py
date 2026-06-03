#!/usr/bin/env python3
"""Generate a viseme animation using Wan 2.2 T2V via RunPod ComfyUI.

Renders a female avatar head showing the mouth shapes for the
viseme sequence: SIL → PP → FF.

  SIL  – silence / neutral: mouth closed, lips relaxed
  PP   – bilabial plosive (P, B, M): lips pressed firmly together
  FF   – labiodental fricative (F, V): upper teeth resting on lower lip

Usage:
    export COMFYUI_URL=https://<pod_id>-8188.proxy.runpod.net
    export RUNPOD_API_KEY=<key>
    python runpod/generate_viseme.py [output.mp4]
"""

import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

COMFYUI_URL = os.environ.get("COMFYUI_URL", "")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

if not COMFYUI_URL:
    sys.exit("Error: COMFYUI_URL environment variable is not set")
if not RUNPOD_API_KEY:
    sys.exit("Error: RUNPOD_API_KEY environment variable is not set")

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# Describe the full viseme sequence in a single prompt so the model renders
# a continuous animation: SIL (neutral closed) → PP (lips pressed together)
# → FF (upper teeth on lower lip).
PROMPT = (
    "Anime-style female avatar, bust portrait centered in frame, "
    "full head including all hair, visible neck and bare shoulders, "
    "soft studio lighting, expressive large eyes, smooth skin, "
    "mouth animation sequence showing three viseme mouth shapes in order: "
    "first the mouth is closed and relaxed in neutral silence (SIL viseme), "
    "then the lips press firmly together in a bilabial plosive shape (PP viseme), "
    "then the upper front teeth rest gently on the lower lip in a labiodental fricative shape (FF viseme), "
    "clean white or soft gradient background, "
    "high quality anime illustration style, consistent character, smooth motion"
)

NEGATIVE = (
    "blurry, low quality, distorted, watermark, text, subtitles, "
    "multiple faces, crowd, body, hands, scenery, background objects, "
    "open mouth screaming, extreme expressions, deformed teeth, "
    "inconsistent character, flickering, noisy"
)

SEED = random.randint(0, 2**32 - 1)

# ---------------------------------------------------------------------------
# Workflow — Wan 2.2 MoE two-pass T2V
# Portrait orientation (480×832) suits a head close-up.
# 81 frames @ 24 fps = 3.375 s — enough time to transition through 3 visemes.
# ---------------------------------------------------------------------------
WIDTH = 480
HEIGHT = 832
FRAMES = 81
STEPS = 30
CFG = 6.0
SHIFT = 5.0
HIGH_NOISE_END = 20
FILENAME_PREFIX = "viseme_anime"

WORKFLOW = {
    # VAE
    "1": {
        "class_type": "WanVideoVAELoader",
        "inputs": {
            "model_name": "wan_2.1_vae.safetensors",
            "precision": "bf16",
        },
    },
    # T5 text encoder
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "type": "wan",
        },
    },
    # Positive prompt
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": PROMPT,
            "clip": ["2", 0],
        },
    },
    # Negative prompt
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": NEGATIVE,
            "clip": ["2", 0],
        },
    },
    # Bridge CONDITIONING → WANVIDEOTEXTEMBEDS
    "5": {
        "class_type": "WanVideoTextEmbedBridge",
        "inputs": {
            "positive": ["3", 0],
            "negative": ["4", 0],
        },
    },
    # High-noise expert (layout / structure)
    "6": {
        "class_type": "WanVideoModelLoader",
        "inputs": {
            "model": "wan2.2_t2v_high_noise_14B_fp16.safetensors",
            "base_precision": "fp16",
            "quantization": "disabled",
            "load_device": "main_device",
        },
    },
    # Low-noise expert (refinement / detail)
    "7": {
        "class_type": "WanVideoModelLoader",
        "inputs": {
            "model": "wan2.2_t2v_low_noise_14B_fp16.safetensors",
            "base_precision": "fp16",
            "quantization": "disabled",
            "load_device": "main_device",
        },
    },
    # Empty video latent (portrait)
    "8": {
        "class_type": "WanVideoEmptyEmbeds",
        "inputs": {
            "width": WIDTH,
            "height": HEIGHT,
            "num_frames": FRAMES,
        },
    },
    # Pass 1: high-noise expert, steps 0–HIGH_NOISE_END (layout)
    "9": {
        "class_type": "WanVideoSampler",
        "inputs": {
            "model": ["6", 0],
            "image_embeds": ["8", 0],
            "text_embeds": ["5", 0],
            "steps": STEPS,
            "cfg": CFG,
            "shift": SHIFT,
            "seed": SEED,
            "force_offload": True,
            "scheduler": "unipc",
            "riflex_freq_index": 0,
            "start_step": 0,
            "end_step": HIGH_NOISE_END,
        },
    },
    # Pass 2: low-noise expert, steps HIGH_NOISE_END–end (refinement)
    "10": {
        "class_type": "WanVideoSampler",
        "inputs": {
            "model": ["7", 0],
            "image_embeds": ["8", 0],
            "text_embeds": ["5", 0],
            "samples": ["9", 0],
            "steps": STEPS,
            "cfg": CFG,
            "shift": SHIFT,
            "seed": SEED,
            "force_offload": True,
            "scheduler": "unipc",
            "riflex_freq_index": 0,
            "start_step": HIGH_NOISE_END,
            "end_step": -1,
        },
    },
    # Decode latents → frames
    "11": {
        "class_type": "WanVideoDecode",
        "inputs": {
            "vae": ["1", 0],
            "samples": ["10", 0],
            "enable_vae_tiling": False,
            "tile_x": 272,
            "tile_y": 272,
            "tile_stride_x": 144,
            "tile_stride_y": 128,
        },
    },
    # Combine frames → mp4
    "12": {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["11", 0],
            "frame_rate": 24,
            "loop_count": 0,
            "filename_prefix": FILENAME_PREFIX,
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True,
        },
    },
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api(method, path, body=None):
    url = f"{COMFYUI_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "User-Agent": "Mozilla/5.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        ct = r.headers.get("Content-Type", "")
        return json.loads(raw) if "json" in ct else raw


def submit():
    print(f"Seed: {SEED}")
    print(f"Resolution: {WIDTH}x{HEIGHT}, {FRAMES} frames @ 24 fps ({FRAMES/24:.2f}s)")
    print(f"Viseme sequence: SIL → PP → FF")
    result = api("POST", "/prompt", {"prompt": WORKFLOW})
    pid = result["prompt_id"]
    print(f"Prompt ID: {pid}")
    return pid


def poll(pid, timeout=600):
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        hist = api("GET", f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            print(f"\nStatus: {status}")
            outputs = entry.get("outputs", {})
            files = []
            for node_out in outputs.values():
                files += node_out.get("gifs", [])
                files += node_out.get("images", [])
            if files:
                return files
            raise RuntimeError(f"Completed with no outputs: {entry}")
        time.sleep(5)
        dots += 1
        print(f"\rWaiting... {dots * 5}s elapsed", end="", flush=True)
    raise TimeoutError(f"Timed out after {timeout}s")


def download(file_info, out_path):
    fn = file_info["filename"]
    sf = file_info.get("subfolder", "")
    ft = file_info.get("type", "output")
    params = f"filename={urllib.parse.quote(fn)}&type={ft}"
    if sf:
        params += f"&subfolder={urllib.parse.quote(sf)}"
    url = f"{COMFYUI_URL}/view?{params}"
    print(f"\nDownloading from {url}")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {RUNPOD_API_KEY}",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Saved {len(data):,} bytes → {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/viseme_anime.mp4"
    pid = submit()
    files = poll(pid, timeout=600)
    print(f"\nOutput files: {files}")
    mp4 = next((f for f in files if f.get("filename", "").endswith(".mp4")), files[0])
    download(mp4, out)
    print(f"\nDone! Video at: {out}")
