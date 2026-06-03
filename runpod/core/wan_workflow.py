import random

# Model filenames present on the RunPod ComfyUI instance
HIGH_NOISE_MODEL = "wan2.2_t2v_high_noise_14B_fp16.safetensors"
LOW_NOISE_MODEL = "wan2.2_t2v_low_noise_14B_fp16.safetensors"
TEXT_ENCODER = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE_MODEL = "wan_2.1_vae.safetensors"

# Split point between high-noise and low-noise expert passes
HIGH_NOISE_END_STEP = 20


def build_t2v_workflow(
    text: str,
    negative_text: str = "blurry, low quality, text artifacts, distorted, watermark, ugly, amateur",
    seed: int = -1,
    width: int = 832,
    height: int = 480,
    frames: int = 81,
    steps: int = 30,
    cfg: float = 6.0,
    shift: float = 5.0,
    filename_prefix: str = "wan_t2v",
) -> dict:
    """Build a Wan 2.2 T2V ComfyUI prompt workflow dict using native Wan video nodes.

    Uses the MoE two-pass sampling approach:
      Pass 1 (steps 0-20): high-noise expert handles layout/structure
      Pass 2 (steps 20-30): low-noise expert handles refinement/detail

    Text encoding uses CLIPLoader (type="wan") + CLIPTextEncode + WanVideoTextEmbedBridge.
    This properly handles the fp8_e4m3fn_scaled T5 model via ComfyUI's native fp8 support
    (the same infrastructure used for FLUX fp8 models).

    Node layout:
       1  WanVideoVAELoader      → loads VAE
       2  CLIPLoader             → loads T5 text encoder (fp8_scaled handled natively)
       3  CLIPTextEncode         → positive conditioning
       4  CLIPTextEncode         → negative conditioning
       5  WanVideoTextEmbedBridge→ CONDITIONING → WANVIDEOTEXTEMBEDS
       6  WanVideoModelLoader    → loads high-noise expert diffusion model
       7  WanVideoModelLoader    → loads low-noise expert diffusion model
       8  WanVideoEmptyEmbeds    → video-shaped latent
       9  WanVideoSampler        → pass 1: high-noise (steps 0-20)
      10  WanVideoSampler        → pass 2: low-noise (steps 20-30)
      11  WanVideoDecode         → latent → frames
      12  VHS_VideoCombine       → frames → mp4
    """
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    return {
        # VAE
        "1": {
            "class_type": "WanVideoVAELoader",
            "inputs": {
                "model_name": VAE_MODEL,
                "precision": "bf16",
            },
        },
        # Standard CLIPLoader with type="wan" — properly handles fp8_scaled format
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": TEXT_ENCODER,
                "type": "wan",
            },
        },
        # Positive prompt encoding
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": text,
                "clip": ["2", 0],
            },
        },
        # Negative prompt encoding
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_text,
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
                "model": HIGH_NOISE_MODEL,
                "base_precision": "fp16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        # Low-noise expert (refinement)
        "7": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": LOW_NOISE_MODEL,
                "base_precision": "fp16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        # Empty video latent
        "8": {
            "class_type": "WanVideoEmptyEmbeds",
            "inputs": {
                "width": width,
                "height": height,
                "num_frames": frames,
            },
        },
        # Pass 1: high-noise expert handles layout (steps 0–HIGH_NOISE_END_STEP)
        "9": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["6", 0],
                "image_embeds": ["8", 0],
                "text_embeds": ["5", 0],
                "steps": steps,
                "cfg": cfg,
                "shift": shift,
                "seed": seed,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "start_step": 0,
                "end_step": HIGH_NOISE_END_STEP,
            },
        },
        # Pass 2: low-noise expert handles refinement (steps HIGH_NOISE_END_STEP–end)
        "10": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["7", 0],
                "image_embeds": ["8", 0],
                "text_embeds": ["5", 0],
                "samples": ["9", 0],
                "steps": steps,
                "cfg": cfg,
                "shift": shift,
                "seed": seed,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "start_step": HIGH_NOISE_END_STEP,
                "end_step": -1,
            },
        },
        # Decode latents to frames
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
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }
