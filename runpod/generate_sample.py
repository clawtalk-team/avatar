#!/usr/bin/env python3
"""Submit a Wan 2.2 T2V job directly to the RunPod ComfyUI instance and download the result.

Quick smoke-test: generates a short presenter video to confirm the ComfyUI pipeline
is working end-to-end before running the heavier avatar generation scripts.

Usage:
    export COMFYUI_URL=https://<pod_id>-8188.proxy.runpod.net
    export RUNPOD_API_KEY=<key>
    python runpod/generate_sample.py [output.mp4]
"""

import json
import os
import random
import sys
import time
import urllib.request

COMFYUI_URL = os.environ.get("COMFYUI_URL", "")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

if not COMFYUI_URL:
    sys.exit("Error: COMFYUI_URL environment variable is not set")
if not RUNPOD_API_KEY:
    sys.exit("Error: RUNPOD_API_KEY environment variable is not set")

PROMPT = (
    "Professional female news presenter in a tailored navy blazer sitting at a sleek modern broadcast news desk, "
    "occupying the LEFT half of the frame, speaking directly to camera with natural confident expression, "
    "warm professional studio lighting, shallow depth of field, "
    "RIGHT half of the frame is a large clean flat white graphic panel card, "
    "solid white rectangular screen filling the right 50 percent of the frame, "
    "broadcast television news production, 4K ultra-sharp, BBC or CNN studio aesthetic"
)

NEGATIVE = (
    "blurry, low quality, distorted, watermark, ugly, amateur, text artifacts, "
    "two people, crowd, outdoor, dark background, busy background, cluttered right side, "
    "colored right panel, patterned right panel"
)

SEED = random.randint(0, 2**32 - 1)

WORKFLOW = {
    # VAE
    "1": {
        "class_type": "WanVideoVAELoader",
        "inputs": {
            "model_name": "wan_2.1_vae.safetensors",
            "precision": "bf16",
        },
    },
    # Standard CLIPLoader with type="wan" — properly handles fp8_scaled format
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "type": "wan",
        },
    },
    # Positive prompt encoding via standard CLIPTextEncode
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": PROMPT,
            "clip": ["2", 0],
        },
    },
    # Negative prompt encoding
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
    # Low-noise expert (refinement)
    "7": {
        "class_type": "WanVideoModelLoader",
        "inputs": {
            "model": "wan2.2_t2v_low_noise_14B_fp16.safetensors",
            "base_precision": "fp16",
            "quantization": "disabled",
            "load_device": "main_device",
        },
    },
    # Empty video latent — 832x480, 81 frames = 3.375s at 24fps
    "8": {
        "class_type": "WanVideoEmptyEmbeds",
        "inputs": {
            "width": 832,
            "height": 480,
            "num_frames": 81,
        },
    },
    # Pass 1: high-noise expert, steps 0-20 (layout)
    "9": {
        "class_type": "WanVideoSampler",
        "inputs": {
            "model": ["6", 0],
            "image_embeds": ["8", 0],
            "text_embeds": ["5", 0],
            "steps": 30,
            "cfg": 6.0,
            "shift": 5.0,
            "seed": SEED,
            "force_offload": True,
            "scheduler": "unipc",
            "riflex_freq_index": 0,
            "start_step": 0,
            "end_step": 20,
        },
    },
    # Pass 2: low-noise expert, steps 20-30 (refinement)
    "10": {
        "class_type": "WanVideoSampler",
        "inputs": {
            "model": ["7", 0],
            "image_embeds": ["8", 0],
            "text_embeds": ["5", 0],
            "samples": ["9", 0],
            "steps": 30,
            "cfg": 6.0,
            "shift": 5.0,
            "seed": SEED,
            "force_offload": True,
            "scheduler": "unipc",
            "riflex_freq_index": 0,
            "start_step": 20,
            "end_step": -1,
        },
    },
    # Decode latents
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
    # Combine frames to mp4
    "12": {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["11", 0],
            "frame_rate": 24,
            "loop_count": 0,
            "filename_prefix": "avatar_sample",
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True,
        },
    },
}


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
    import urllib.parse
    fn = file_info["filename"]
    sf = file_info.get("subfolder", "")
    ft = file_info.get("type", "output")
    params = f"filename={urllib.parse.quote(fn)}&type={ft}"
    if sf:
        params += f"&subfolder={urllib.parse.quote(sf)}"
    url = f"{COMFYUI_URL}/view?{params}"
    print(f"\nDownloading from {url}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {RUNPOD_API_KEY}", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Saved {len(data):,} bytes → {out_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/avatar_sample.mp4"
    pid = submit()
    files = poll(pid, timeout=600)
    print(f"\nOutput files: {files}")
    mp4 = next((f for f in files if f.get("filename", "").endswith(".mp4")), files[0])
    download(mp4, out)
    print(f"\nDone! Video at: {out}")
