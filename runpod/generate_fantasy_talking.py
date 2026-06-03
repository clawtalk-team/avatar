#!/usr/bin/env python3
"""Generate an audio-driven talking portrait using FantasyTalking via Wan 2.2 I2V.

FantasyTalking drives mouth/face animation directly from an audio waveform.
No per-viseme keyframes needed — the audio conditioning handles timing.

Node graph:
  FantasyTalkingModelLoader ──────────────────────────────────────────┐
       │                                                               │
       ▼                                                               ▼
  WanVideoModelLoader (I2V high, fantasytalking_model)    FantasyTalkingWav2VecEmbeds
       │                                            ▲         ▲          │
  WanVideoModelLoader (I2V low)     Wav2VecModel ──┘         │          │
       │                                         LoadAudio ──┘          │
  LoadWanVideoT5TextEncoder                                             │
       │                                                                │
  WanVideoTextEncode (pos + neg)                                        │
       │                                                                │
  WanVideoImageToVideoEncode (start_image)                              │
       │                                                                │
  WanVideoSampler (high-noise pass) ◄───── fantasytalking_embeds ──────┘
       │
  WanVideoSampler (low-noise pass)
       │
  WanVideoDecode → VHS_VideoCombine (mp4 with audio)

Usage:
    export COMFYUI_URL=https://<pod_id>-8188.proxy.runpod.net
    export RUNPOD_API_KEY=<key>
    python runpod/generate_fantasy_talking.py [audio.wav] [portrait.png] [output.mp4]

    Defaults:
      audio   – generates macOS TTS speech if not provided
      portrait – uses /tmp/viseme_i2v/sil_base_frame0.png if it exists
                 (run generate_viseme_i2v.py first to create it)
      output  – /tmp/fantasy_talking.mp4
"""

import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

COMFYUI_URL = os.environ.get("COMFYUI_URL", "")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

if not COMFYUI_URL:
    sys.exit("Error: COMFYUI_URL not set")
if not RUNPOD_API_KEY:
    sys.exit("Error: RUNPOD_API_KEY not set")

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
AUDIO_PATH    = sys.argv[1] if len(sys.argv) > 1 else None
PORTRAIT_PATH = sys.argv[2] if len(sys.argv) > 2 else "/tmp/viseme_i2v/sil_base_frame0.png"
OUT_PATH      = sys.argv[3] if len(sys.argv) > 3 else "/tmp/fantasy_talking.mp4"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
POSITIVE = (
    "photorealistic female avatar, professional portrait, full head with long dark hair, "
    "visible neck and bare shoulders, soft studio lighting, speaking naturally, "
    "clean white background, sharp focus, high quality"
)
NEGATIVE = (
    "blurry, low quality, distorted, watermark, text, multiple people, "
    "deformed face, inconsistent character, flickering, noisy"
)

SEED = random.randint(0, 2**32 - 1)

# Resolution and frames
WIDTH, HEIGHT = 480, 832
FPS = 23.0
STEPS = 30
CFG = 6.0
SHIFT = 5.0
HIGH_NOISE_END = 20

# Models
I2V_HIGH = "wan2.2_i2v_high_noise_14B_fp16.safetensors"
I2V_LOW  = "wan2.2_i2v_low_noise_14B_fp16.safetensors"
TEXT_ENC = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE      = "wan_2.1_vae.safetensors"
WAV2VEC  = "facebook/wav2vec2-base-960h"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _auth_headers(content_type="application/json"):
    return {
        "Content-Type": content_type,
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "User-Agent": "Mozilla/5.0",
    }


def api_json(method, path, body=None):
    url = f"{COMFYUI_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=_auth_headers(), method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def api_binary(path):
    req = urllib.request.Request(
        f"{COMFYUI_URL}{path}",
        headers={"Authorization": f"Bearer {RUNPOD_API_KEY}", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def upload_file(file_bytes, filename, mime_type):
    """Upload bytes to ComfyUI /upload/image (works for images and audio)."""
    boundary = "----ComfyUpload"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
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
                raise RuntimeError(f"{label} completed with no outputs: {entry}")
        time.sleep(5)
        dots += 1
        print(f"\r  {label} {dots * 5}s...", end="", flush=True)
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
# Audio preparation
# ---------------------------------------------------------------------------

def prepare_audio(audio_path):
    """Return (wav_bytes, duration_seconds). Generates TTS if path is None."""
    if audio_path and os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            wav_bytes = f.read()
    else:
        print("  Generating TTS audio with macOS `say`...")
        aiff = "/tmp/_ft_tts.aiff"
        wav  = "/tmp/_ft_tts.wav"
        text = "The quick brown fox jumps over the lazy dog. She sells sea shells by the sea shore."
        subprocess.run(["say", "-o", aiff, text], check=True)
        subprocess.run(["afconvert", aiff, "-d", "LEI16@16000", "-f", "WAVE", wav], check=True)
        with open(wav, "rb") as f:
            wav_bytes = f.read()
        audio_path = wav

    import wave, io
    with wave.open(io.BytesIO(wav_bytes)) as w:
        duration = w.getnframes() / w.getframerate()
    print(f"  Audio: {len(wav_bytes):,} bytes, {duration:.2f}s")
    return wav_bytes, duration


# ---------------------------------------------------------------------------
# Workflow builder
# ---------------------------------------------------------------------------

def build_workflow(audio_server_name, portrait_server_name, num_frames):
    return {
        # ── FantasyTalking model (patches I2V for audio conditioning) ──────
        # NOTE: this is the dedicated adapter checkpoint, NOT the base Wan I2V model
        "1": {
            "class_type": "FantasyTalkingModelLoader",
            "inputs": {
                "model": "fantasytalking_model.ckpt",
                "base_precision": "fp16",
            },
        },
        # ── Text encoder ───────────────────────────────────────────────────
        "2": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {
                "model_name": TEXT_ENC,
                "precision": "bf16",
                "load_device": "offload_device",
            },
        },
        "3": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": POSITIVE,
                "negative_prompt": NEGATIVE,
                "t5": ["2", 0],
                "force_offload": True,
            },
        },
        # ── VAE ────────────────────────────────────────────────────────────
        "4": {
            "class_type": "WanVideoVAELoader",
            "inputs": {"model_name": VAE, "precision": "bf16"},
        },
        # ── I2V model (high-noise, patched with FantasyTalking) ────────────
        "5": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": I2V_HIGH,
                "base_precision": "fp16",
                "quantization": "disabled",
                "load_device": "main_device",
                "fantasytalking_model": ["1", 0],
            },
        },
        # ── I2V model (low-noise, no FantasyTalking patch) ─────────────────
        "6": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": I2V_LOW,
                "base_precision": "fp16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        # ── Wav2Vec audio encoder (downloads from HuggingFace if needed) ───
        "7": {
            "class_type": "DownloadAndLoadWav2VecModel",
            "inputs": {
                "model": WAV2VEC,
                "base_precision": "fp16",
                "load_device": "main_device",
            },
        },
        # ── Load uploaded audio file ────────────────────────────────────────
        "8": {
            "class_type": "LoadAudio",
            "inputs": {"audio": audio_server_name},
        },
        # ── FantasyTalking audio conditioning ───────────────────────────────
        "9": {
            "class_type": "FantasyTalkingWav2VecEmbeds",
            "inputs": {
                "wav2vec_model": ["7", 0],
                "fantasytalking_model": ["1", 0],
                "audio": ["8", 0],
                "num_frames": num_frames,
                "fps": FPS,
                "audio_scale": 1.0,
                "audio_cfg_scale": 1.0,
            },
        },
        # ── Portrait image ──────────────────────────────────────────────────
        "10": {
            "class_type": "LoadImage",
            "inputs": {"image": portrait_server_name},
        },
        # ── I2V latent encode (start from portrait) ─────────────────────────
        "11": {
            "class_type": "WanVideoImageToVideoEncode",
            "inputs": {
                "width": WIDTH,
                "height": HEIGHT,
                "num_frames": num_frames,
                "noise_aug_strength": 0.0,
                "start_latent_strength": 1.0,
                "end_latent_strength": 1.0,
                "force_offload": True,
                "vae": ["4", 0],
                "start_image": ["10", 0],
            },
        },
        # ── Sampling — high-noise pass (with FantasyTalking embeds) ─────────
        "12": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["5", 0],
                "text_embeds": ["3", 0],
                "image_embeds": ["11", 0],
                "steps": STEPS,
                "cfg": CFG,
                "shift": SHIFT,
                "seed": SEED,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "start_step": 0,
                "end_step": HIGH_NOISE_END,
                "fantasytalking_embeds": ["9", 0],
            },
        },
        # ── Sampling — low-noise pass ────────────────────────────────────────
        "13": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["6", 0],
                "text_embeds": ["3", 0],
                "image_embeds": ["11", 0],
                "samples": ["12", 0],
                "steps": STEPS,
                "cfg": CFG,
                "shift": SHIFT,
                "seed": SEED,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "start_step": HIGH_NOISE_END,
                "end_step": -1,
                "fantasytalking_embeds": ["9", 0],
            },
        },
        # ── Decode ───────────────────────────────────────────────────────────
        "14": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae": ["4", 0],
                "samples": ["13", 0],
                "enable_vae_tiling": False,
                "tile_x": 272, "tile_y": 272,
                "tile_stride_x": 144, "tile_stride_y": 128,
            },
        },
        # ── Combine frames → mp4 (with original audio embedded) ──────────────
        "15": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["14", 0],
                "audio": ["8", 0],
                "frame_rate": FPS,
                "loop_count": 0,
                "filename_prefix": "fantasy_talking",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Seed: {SEED}")
    print(f"Portrait: {PORTRAIT_PATH}")

    # ── Audio ──────────────────────────────────────────────────────────────
    print("\n[1/4] Preparing audio...")
    wav_bytes, duration = prepare_audio(AUDIO_PATH)
    num_frames = max(25, int(duration * FPS))
    print(f"  Frames: {num_frames} ({num_frames / FPS:.2f}s @ {FPS} fps)")

    audio_server_name = upload_file(wav_bytes, "ft_audio.wav", "audio/wav")

    # ── Portrait ────────────────────────────────────────────────────────────
    print("\n[2/4] Uploading portrait...")
    if os.path.exists(PORTRAIT_PATH):
        with open(PORTRAIT_PATH, "rb") as f:
            portrait_bytes = f.read()
    else:
        sys.exit(
            f"Portrait not found: {PORTRAIT_PATH}\n"
            f"Run generate_viseme_i2v.py first to create the base portrait."
        )

    portrait_server_name = upload_file(portrait_bytes, "ft_portrait.png", "image/png")

    # ── Submit ──────────────────────────────────────────────────────────────
    print("\n[3/4] Submitting FantasyTalking workflow...")
    wf = build_workflow(audio_server_name, portrait_server_name, num_frames)
    result = api_json("POST", "/prompt", {"prompt": wf})
    pid = result["prompt_id"]
    print(f"  Prompt ID: {pid}")
    print(f"  Generating {num_frames} frames — expect ~5-8 min on RTX 6000")

    # ── Poll & download ─────────────────────────────────────────────────────
    print("\n[4/4] Waiting for completion...")
    files = poll(pid, timeout=900, label="FantasyTalking")
    print(f"\n  Output files: {[f['filename'] for f in files]}")

    mp4 = next((f for f in files if f.get("filename", "").endswith(".mp4")), files[0])
    download_file(mp4, OUT_PATH)
    print(f"\nDone! Video at: {OUT_PATH}")


if __name__ == "__main__":
    main()
