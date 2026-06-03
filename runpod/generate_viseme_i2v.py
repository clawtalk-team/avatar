#!/usr/bin/env python3
"""Generate consistent per-viseme images and transition clips using Wan 2.2 I2V.

Strategy:
  1. T2V  → generate base SIL (neutral, mouth closed) portrait → extract frame 0
  2. I2V  → start from SIL frame, text = PP (lips pressed together)
               → video IS the SIL→PP transition clip; last frame IS the PP still
  3. I2V  → start from PP frame, text = FF (upper teeth on lower lip)
               → video IS the PP→FF transition clip; last frame IS the FF still
  4. I2V  → start from FF frame, text = SIL (return to neutral)
               → video IS the FF→SIL transition clip (for looping)

Character consistency is enforced because each I2V is anchored to the previous
viseme's last frame — every frame in the sequence shares the same pixel identity
outside the mouth region.

The SIL base portrait (frame 0) is also the input image for FantasyTalking
(generate_fantasy_talking.py), which drives full audio-conditioned lip sync.

Usage:
    export COMFYUI_URL=https://<pod_id>-8188.proxy.runpod.net
    export RUNPOD_API_KEY=<key>
    python runpod/generate_viseme_i2v.py [output_dir]
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import random

COMFYUI_URL = os.environ.get("COMFYUI_URL", "")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

if not COMFYUI_URL:
    sys.exit("Error: COMFYUI_URL environment variable is not set")
if not RUNPOD_API_KEY:
    sys.exit("Error: RUNPOD_API_KEY environment variable is not set")

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/viseme_i2v"
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Character description — shared across all phases for consistency
# ---------------------------------------------------------------------------
CHARACTER = (
    "photorealistic female avatar, professional portrait, full head with long dark hair, "
    "visible neck and bare shoulders, soft studio lighting, neutral expression, "
    "clean white background, sharp focus, high quality"
)
NEGATIVE = (
    "blurry, low quality, distorted, watermark, text, multiple people, "
    "deformed face, inconsistent character, flickering, noisy, body below shoulders"
)

# Viseme mouth descriptions — appended to CHARACTER for each phase
VISEME_PROMPTS = {
    "SIL": "mouth closed, lips relaxed and together in neutral silence",
    "PP":  "lips pressed firmly together, bilabial closure, mouth completely closed with slight pressure",
    "FF":  "upper front teeth resting gently on lower lip, labiodental contact, slight smile",
}

SEED = random.randint(0, 2**32 - 1)
print(f"Seed: {SEED}")

# Resolution and frame counts
WIDTH, HEIGHT = 480, 832   # portrait
T2V_FRAMES = 5             # minimal T2V — just enough to get a stable portrait frame
I2V_FRAMES = 25            # ~1 second per transition @ 24 fps
STEPS = 30
CFG = 6.0
SHIFT = 5.0
HIGH_NOISE_END = 20

# Model names
T2V_HIGH  = "wan2.2_t2v_high_noise_14B_fp16.safetensors"
T2V_LOW   = "wan2.2_t2v_low_noise_14B_fp16.safetensors"
I2V_HIGH  = "wan2.2_i2v_high_noise_14B_fp16.safetensors"
I2V_LOW   = "wan2.2_i2v_low_noise_14B_fp16.safetensors"
TEXT_ENC  = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE       = "wan_2.1_vae.safetensors"


# ---------------------------------------------------------------------------
# ComfyUI API helpers
# ---------------------------------------------------------------------------

def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "User-Agent": "Mozilla/5.0",
    }


def api_json(method, path, body=None):
    url = f"{COMFYUI_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_binary(path):
    url = f"{COMFYUI_URL}{path}"
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "User-Agent": "Mozilla/5.0",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def upload_image(image_bytes, filename):
    """Upload PNG bytes to ComfyUI /upload/image and return the server filename."""
    boundary = "----ComfyBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()

    url = f"{COMFYUI_URL}/upload/image"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {RUNPOD_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    print(f"  Uploaded {filename} → {result['name']}")
    return result["name"]


def submit_workflow(workflow):
    result = api_json("POST", "/prompt", {"prompt": workflow})
    return result["prompt_id"]


def poll(prompt_id, timeout=600, label=""):
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        hist = api_json("GET", f"/history/{prompt_id}")
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"{label} failed: {status}")
            outputs = entry.get("outputs", {})
            files = []
            for node_out in outputs.values():
                files += node_out.get("gifs", [])
                files += node_out.get("images", [])
            if files:
                return files
            if status.get("completed"):
                raise RuntimeError(f"{label} completed with no outputs")
        time.sleep(5)
        dots += 1
        print(f"\r  {label} waiting... {dots * 5}s", end="", flush=True)
    raise TimeoutError(f"{label} timed out after {timeout}s")


def download_file(file_info, out_path):
    fn = file_info["filename"]
    sf = file_info.get("subfolder", "")
    ft = file_info.get("type", "output")
    params = f"filename={urllib.parse.quote(fn)}&type={ft}"
    if sf:
        params += f"&subfolder={urllib.parse.quote(sf)}"
    data = api_binary(f"/view?{params}")
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"\n  Saved {len(data):,} bytes → {out_path}")
    return data


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def _common_nodes(positive_text):
    """Nodes 1-5: VAE, text encoder, conditioning (shared between T2V and I2V)."""
    return {
        "1": {"class_type": "WanVideoVAELoader",
              "inputs": {"model_name": VAE, "precision": "bf16"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXT_ENC, "type": "wan"}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": positive_text, "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "5": {"class_type": "WanVideoTextEmbedBridge",
              "inputs": {"positive": ["3", 0], "negative": ["4", 0]}},
    }


def build_t2v_workflow(viseme_key, filename_prefix):
    """T2V workflow — generates frames saved as PNG. Used for the initial SIL portrait."""
    prompt = f"{CHARACTER}, {VISEME_PROMPTS[viseme_key]}"
    wf = _common_nodes(prompt)
    wf.update({
        "6": {"class_type": "WanVideoModelLoader",
              "inputs": {"model": T2V_HIGH, "base_precision": "fp16",
                         "quantization": "disabled", "load_device": "main_device"}},
        "7": {"class_type": "WanVideoModelLoader",
              "inputs": {"model": T2V_LOW, "base_precision": "fp16",
                         "quantization": "disabled", "load_device": "main_device"}},
        "8": {"class_type": "WanVideoEmptyEmbeds",
              "inputs": {"width": WIDTH, "height": HEIGHT, "num_frames": T2V_FRAMES}},
        "9": {"class_type": "WanVideoSampler",
              "inputs": {"model": ["6", 0], "image_embeds": ["8", 0],
                         "text_embeds": ["5", 0], "steps": STEPS,
                         "cfg": CFG, "shift": SHIFT, "seed": SEED,
                         "force_offload": True, "scheduler": "unipc",
                         "riflex_freq_index": 0, "start_step": 0,
                         "end_step": HIGH_NOISE_END}},
        "10": {"class_type": "WanVideoSampler",
               "inputs": {"model": ["7", 0], "image_embeds": ["8", 0],
                          "text_embeds": ["5", 0], "samples": ["9", 0],
                          "steps": STEPS, "cfg": CFG, "shift": SHIFT, "seed": SEED,
                          "force_offload": True, "scheduler": "unipc",
                          "riflex_freq_index": 0, "start_step": HIGH_NOISE_END,
                          "end_step": -1}},
        "11": {"class_type": "WanVideoDecode",
               "inputs": {"vae": ["1", 0], "samples": ["10", 0],
                          "enable_vae_tiling": False,
                          "tile_x": 272, "tile_y": 272,
                          "tile_stride_x": 144, "tile_stride_y": 128}},
        # Save ALL frames as PNG so we can download frame 0
        "12": {"class_type": "SaveImage",
               "inputs": {"images": ["11", 0],
                          "filename_prefix": filename_prefix}},
    })
    return wf


def build_i2v_workflow(viseme_key, start_image_name, filename_prefix, video_prefix):
    """I2V workflow — starts from an uploaded image, animates toward the viseme description.

    Outputs:
      - PNG frames (SaveImage) — the last frame is the target viseme still
      - MP4 clip (VHS_VideoCombine) — the full transition clip
    """
    prompt = f"{CHARACTER}, {VISEME_PROMPTS[viseme_key]}"
    wf = _common_nodes(prompt)
    wf.update({
        "6": {"class_type": "WanVideoModelLoader",
              "inputs": {"model": I2V_HIGH, "base_precision": "fp16",
                         "quantization": "disabled", "load_device": "main_device"}},
        "7": {"class_type": "WanVideoModelLoader",
              "inputs": {"model": I2V_LOW, "base_precision": "fp16",
                         "quantization": "disabled", "load_device": "main_device"}},
        # Load the anchor frame uploaded to ComfyUI
        "8": {"class_type": "LoadImage",
              "inputs": {"image": start_image_name}},
        # Encode start image into latent space; noise_aug_strength=0 for maximum identity lock
        "9": {"class_type": "WanVideoImageToVideoEncode",
              "inputs": {"width": WIDTH, "height": HEIGHT, "num_frames": I2V_FRAMES,
                         "noise_aug_strength": 0.0,
                         "start_latent_strength": 1.0,
                         "end_latent_strength": 1.0,
                         "force_offload": True,
                         "vae": ["1", 0],
                         "start_image": ["8", 0]}},
        "10": {"class_type": "WanVideoSampler",
               "inputs": {"model": ["6", 0], "image_embeds": ["9", 0],
                          "text_embeds": ["5", 0], "steps": STEPS,
                          "cfg": CFG, "shift": SHIFT, "seed": SEED,
                          "force_offload": True, "scheduler": "unipc",
                          "riflex_freq_index": 0, "start_step": 0,
                          "end_step": HIGH_NOISE_END}},
        "11": {"class_type": "WanVideoSampler",
               "inputs": {"model": ["7", 0], "image_embeds": ["9", 0],
                          "text_embeds": ["5", 0], "samples": ["10", 0],
                          "steps": STEPS, "cfg": CFG, "shift": SHIFT, "seed": SEED,
                          "force_offload": True, "scheduler": "unipc",
                          "riflex_freq_index": 0, "start_step": HIGH_NOISE_END,
                          "end_step": -1}},
        "12": {"class_type": "WanVideoDecode",
               "inputs": {"vae": ["1", 0], "samples": ["11", 0],
                          "enable_vae_tiling": False,
                          "tile_x": 272, "tile_y": 272,
                          "tile_stride_x": 144, "tile_stride_y": 128}},
        # Save all frames as PNG — we'll pick the last one as the target viseme still
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0],
                          "filename_prefix": filename_prefix}},
        # Also save the full transition as mp4
        "14": {"class_type": "VHS_VideoCombine",
               "inputs": {"images": ["12", 0], "frame_rate": 24, "loop_count": 0,
                          "filename_prefix": video_prefix, "format": "video/h264-mp4",
                          "pingpong": False, "save_output": True}},
    })
    return wf


# ---------------------------------------------------------------------------
# Helpers to pick files by name pattern
# ---------------------------------------------------------------------------

def png_files(files):
    return [f for f in files if f.get("filename", "").endswith(".png")]


def mp4_files(files):
    return [f for f in files if f.get("filename", "").endswith(".mp4")]


def first_png(files):
    pngs = sorted(png_files(files), key=lambda f: f["filename"])
    if not pngs:
        raise RuntimeError("No PNG outputs found")
    return pngs[0]


def last_png(files):
    pngs = sorted(png_files(files), key=lambda f: f["filename"])
    if not pngs:
        raise RuntimeError("No PNG outputs found")
    return pngs[-1]


def first_mp4(files):
    mp4s = mp4_files(files)
    if not mp4s:
        raise RuntimeError("No MP4 outputs found")
    return mp4s[0]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print(f"\n{'='*60}")
    print(f"Viseme I2V Pipeline — seed {SEED}")
    print(f"Output dir: {OUT_DIR}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Phase 1: T2V → SIL base portrait
    # ------------------------------------------------------------------
    print("[1/4] Generating SIL base portrait (T2V)...")
    wf = build_t2v_workflow("SIL", "viseme_i2v_sil_base")
    pid = submit_workflow(wf)
    print(f"  Prompt ID: {pid}")
    files = poll(pid, timeout=600, label="T2V SIL")
    print(f"\n  Output files: {[f['filename'] for f in files]}")

    # Download frame 0 as the anchor image
    frame0 = first_png(files)
    base_path = os.path.join(OUT_DIR, "sil_base_frame0.png")
    base_bytes = download_file(frame0, base_path)

    # Upload the base frame back to ComfyUI for I2V use
    print("  Uploading SIL base frame to ComfyUI...")
    sil_server_name = upload_image(base_bytes, "sil_base_frame0.png")

    # ------------------------------------------------------------------
    # Phase 2: I2V SIL → PP
    # ------------------------------------------------------------------
    print("\n[2/4] Generating SIL→PP transition (I2V)...")
    wf = build_i2v_workflow("PP", sil_server_name, "viseme_i2v_pp_frames", "transition_sil_to_pp")
    pid = submit_workflow(wf)
    print(f"  Prompt ID: {pid}")
    files = poll(pid, timeout=600, label="I2V SIL→PP")
    print(f"\n  Output files: {[f['filename'] for f in files]}")

    # Save the transition clip
    sil_pp_mp4 = first_mp4(files)
    download_file(sil_pp_mp4, os.path.join(OUT_DIR, "transition_sil_to_pp.mp4"))

    # The last PNG frame is the PP still image
    pp_frame = last_png(files)
    pp_path = os.path.join(OUT_DIR, "pp_still.png")
    pp_bytes = download_file(pp_frame, pp_path)

    # Upload PP frame for next I2V pass
    print("  Uploading PP frame to ComfyUI...")
    pp_server_name = upload_image(pp_bytes, "pp_still.png")

    # ------------------------------------------------------------------
    # Phase 3: I2V PP → FF
    # ------------------------------------------------------------------
    print("\n[3/4] Generating PP→FF transition (I2V)...")
    wf = build_i2v_workflow("FF", pp_server_name, "viseme_i2v_ff_frames", "transition_pp_to_ff")
    pid = submit_workflow(wf)
    print(f"  Prompt ID: {pid}")
    files = poll(pid, timeout=600, label="I2V PP→FF")
    print(f"\n  Output files: {[f['filename'] for f in files]}")

    download_file(first_mp4(files), os.path.join(OUT_DIR, "transition_pp_to_ff.mp4"))

    ff_frame = last_png(files)
    ff_path = os.path.join(OUT_DIR, "ff_still.png")
    ff_bytes = download_file(ff_frame, ff_path)

    # Upload FF frame for the loop-back pass
    print("  Uploading FF frame to ComfyUI...")
    ff_server_name = upload_image(ff_bytes, "ff_still.png")

    # ------------------------------------------------------------------
    # Phase 4: I2V FF → SIL (return to neutral, for looping)
    # ------------------------------------------------------------------
    print("\n[4/4] Generating FF→SIL transition (I2V, loop-back)...")
    wf = build_i2v_workflow("SIL", ff_server_name, "viseme_i2v_sil_frames", "transition_ff_to_sil")
    pid = submit_workflow(wf)
    print(f"  Prompt ID: {pid}")
    files = poll(pid, timeout=600, label="I2V FF→SIL")
    print(f"\n  Output files: {[f['filename'] for f in files]}")

    download_file(first_mp4(files), os.path.join(OUT_DIR, "transition_ff_to_sil.mp4"))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("Done! Output files:")
    for name in sorted(os.listdir(OUT_DIR)):
        path = os.path.join(OUT_DIR, name)
        print(f"  {name}  ({os.path.getsize(path):,} bytes)")
    print(f"\nViseme stills:")
    print(f"  SIL → {base_path}")
    print(f"  PP  → {pp_path}")
    print(f"  FF  → {ff_path}")
    print(f"\nTransition clips:")
    print(f"  SIL→PP → {OUT_DIR}/transition_sil_to_pp.mp4")
    print(f"  PP→FF  → {OUT_DIR}/transition_pp_to_ff.mp4")
    print(f"  FF→SIL → {OUT_DIR}/transition_ff_to_sil.mp4")
    print(f"\nNext step: run generate_fantasy_talking.py with {base_path} as the portrait input.")


if __name__ == "__main__":
    main()
