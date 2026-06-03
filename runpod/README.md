# RunPod Avatar Generation

Wan 2.2 MoE video generation pipeline for producing photorealistic avatar portraits
and audio-driven lip sync videos, via a RunPod ComfyUI pod.

## Setup

### 1. Configure environment

Add your credentials to `.env` at the project root:

```
RUNPOD_API_KEY=<your runpod api key>
RUNPOD_POD_ID=<your pod id>
```

### 2. Start the pod

```bash
python runpod/pod.py start
```

Once running, export the ComfyUI URL:

```bash
export COMFYUI_URL=$(python runpod/pod.py url)
export RUNPOD_API_KEY=<your key>
```

### 3. Smoke test

Confirm the pipeline works end-to-end:

```bash
python runpod/generate_sample.py /tmp/sample.mp4
```

This generates a short presenter video (~3.4s) and downloads it.

---

## Generation pipeline

### Step 1: Generate avatar portrait (I2V)

Produces a photorealistic avatar with consistent character across viseme transitions:

```bash
python runpod/generate_viseme_i2v.py /tmp/viseme_i2v
```

Outputs to `/tmp/viseme_i2v/`:
- `sil_base_frame0.png` — neutral portrait (used as input for FantasyTalking)
- `transition_sil_to_pp.mp4` — SIL→PP mouth transition
- `transition_pp_to_ff.mp4` — PP→FF mouth transition
- `transition_ff_to_sil.mp4` — FF→SIL loop-back
- `pp_still.png`, `ff_still.png` — individual viseme stills

### Step 2: Generate audio-driven lip sync (FantasyTalking)

Takes an audio file and the portrait from Step 1, outputs a talking head video:

```bash
python runpod/generate_fantasy_talking.py \
    outputs/lipsync/audio.mp3 \
    /tmp/viseme_i2v/sil_base_frame0.png \
    /tmp/avatar_talking.mp4
```

Arguments:
- `audio` — WAV or MP3 file. Omit to use a macOS TTS fallback (requires `say` + `afconvert`).
- `portrait` — PNG portrait, defaults to `/tmp/viseme_i2v/sil_base_frame0.png`
- `output` — destination MP4, defaults to `/tmp/fantasy_talking.mp4`

FantasyTalking drives mouth animation directly from the audio waveform via Wav2Vec
embeddings — no manual viseme keyframing required.

### T2V viseme sequence (optional, simpler)

For a quick non-anchored viseme animation:

```bash
python runpod/generate_viseme.py /tmp/viseme_anime.mp4
```

Generates a single 3.4s clip showing SIL→PP→FF in a single T2V pass (less character
consistency than the I2V pipeline).

---

## Pod management

```bash
python runpod/pod.py status   # show pod status and URL
python runpod/pod.py start    # resume the pod
python runpod/pod.py stop     # stop the pod (models preserved on network volume)
python runpod/pod.py url      # print the ComfyUI proxy URL
```

Stop the pod when not generating — billing is per hour.

---

## Architecture

```
pod.py                  RunPod pod lifecycle (start/stop/status/url)
generate_sample.py      T2V smoke test — presenter video
generate_viseme.py      T2V viseme sequence (SIL→PP→FF, single pass)
generate_viseme_i2v.py  I2V 4-phase pipeline — consistent avatar + viseme stills
generate_fantasy_talking.py  Audio-driven lip sync via FantasyTalking + Wav2Vec

core/
  comfyui_client.py     ComfyUI REST client (submit, poll, download)
  wan_workflow.py       Wan 2.2 T2V workflow builder

docs/
  runpod-video.md       RunPod + Wan 2.2 deployment spec
  runpod-audio.md       Audio generation model research (ACE-Step, MusicGen, etc.)
```

### Model versions

| File | Purpose |
|---|---|
| `wan2.2_t2v_high_noise_14B_fp16.safetensors` | T2V layout pass (steps 0–20) |
| `wan2.2_t2v_low_noise_14B_fp16.safetensors` | T2V refinement pass (steps 20–30) |
| `wan2.2_i2v_high_noise_14B_fp16.safetensors` | I2V layout pass |
| `wan2.2_i2v_low_noise_14B_fp16.safetensors` | I2V refinement pass |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | T5 text encoder |
| `wan_2.1_vae.safetensors` | VAE |
| `fantasytalking_model.ckpt` | FantasyTalking audio adapter |
| `facebook/wav2vec2-base-960h` | Wav2Vec (downloaded from HuggingFace) |

All weights must be present on the pod's network volume under
`/workspace/ComfyUI/models/`. See `docs/runpod-video.md` for setup instructions.
