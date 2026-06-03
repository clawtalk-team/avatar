# AI Music & Sound Effect Generation on RunPod

Research date: 2026-06-02

## Summary

No audio generation model requires more than ~20GB VRAM. The RTX Pro 6000 (96GB) is extreme overkill. The sweet spot for this workload is a **24GB card** — enough for any single model at full quality — or a **48GB card** if running two models simultaneously.

**Recommended GPU:** RTX A5000 (24GB) at **$0.27/hr** — best price for the VRAM needed. Step up to RTX A6000 (48GB) at **$0.44/hr** for multi-model workflows.

**Top model recommendations:**
- **Music (full songs):** ACE-Step 1.5 XL — best quality/license combo, Apache 2.0, ComfyUI support
- **Music (simpler, battle-tested):** MusicGen Large — MIT license, most documented, best ecosystem
- **Sound effects:** Stable Audio Open (SFX variant) or AudioGen — both solid, different strengths
- **Container:** `ashleykleynhans/tts-webui-docker` is the most complete off-the-shelf image

---

## GPU Selection

All models listed below run on 16–20GB VRAM. A 24GB card handles every model with headroom; 48GB lets you run two models simultaneously.

| GPU | VRAM | Price/hr | Verdict |
|---|---|---|---|
| RTX 3090 | 24GB | ~$0.22 | Cheapest option; handles all models; older arch but fine for inference |
| RTX A5000 | 24GB | ~$0.27 | **Best value** — professional GPU, stable, same VRAM as 4090 at 2.6× less cost |
| RTX A6000 | 48GB | ~$0.44 | Best for multi-model; run MusicGen + AudioGen simultaneously |
| L40S | 48GB | ~$0.79 | Faster than A6000, same VRAM; worth it if inference speed matters |
| RTX 4090 | 24GB | ~$0.69 | Fastest 24GB card; 2.6× more expensive than A5000 for same VRAM |
| A100 SXM | 80GB | ~$1.49 | Overkill; only worthwhile for YuE multi-session (80GB+) |
| RTX Pro 6000 | 96GB | N/A | Rarely listed on RunPod; enterprise only; massively over-provisioned |

**Recommendation by workflow:**
- **Single model, cost-sensitive:** RTX A5000 ($0.27/hr)
- **Single model, fastest inference:** L40S ($0.79/hr)
- **Two models simultaneously:** RTX A6000 ($0.44/hr)
- **YuE multi-session full-song (80GB+ needed):** A100 SXM ($1.49/hr) — only edge case requiring >48GB

---

## Music Generation Models

### ACE-Step 1.5 (Recommended — 2026)

| Property | Details |
|---|---|
| Parameters | 2B (standard), 4B (XL, released April 2026) |
| VRAM (XL) | 20GB without offload; 12GB with quantization/offload |
| Max length | Full songs |
| License | **Apache 2.0** (commercial, no restrictions) |
| GitHub | `ace-step/ACE-Step-1.5` (~2,000+ stars, actively maintained) |
| Docker | `ghcr.io/dotnetautor/ace-step-1.5-docker:latest` |
| RunPod | Community templates available |
| ComfyUI | Yes — official nodes (May 2026) |
| Inference speed | <2s on A100; 5-10s on 3090/4090 |

**Strengths:** Highest quality among open models as of 2026, multi-platform (CUDA/ROCm/MLX/Intel), very low VRAM requirements relative to quality. Beats commercial alternatives in benchmarks.

**Weaknesses:** Newer project, less ecosystem documentation than MusicGen.

---

### YuE (Full-song, 2025)

| Property | Details |
|---|---|
| Parameters | 7B |
| VRAM | 16GB fp16; 80GB+ for multi-session full-song |
| Max length | Full songs (3+ minutes) |
| License | **Apache 2.0** (commercial, no restrictions) |
| GitHub | `multimodal-art-projection/YuE` (~2,000+ stars) |
| Docker | `olilanz/ai-yue-gp` (Docker Hub) |
| RunPod | Community deployments available |
| ComfyUI | No official nodes |
| Inference speed | ~5 min for 3-min track on L40S |

**Strengths:** First practical open-source lyrics-to-full-song model (Suno alternative). Supports music continuation, dual-track inference. 27GB Docker image + 27GB cached weights.

**Weaknesses:** Slow inference, no ComfyUI support, heavier than ACE-Step for quality parity.

---

### MusicGen Large (Meta AudioCraft — Battle-tested)

| Property | Details |
|---|---|
| Parameters | ~3.5B |
| VRAM | 16GB |
| Max length | 30–120 seconds |
| License | **MIT** (commercial, fully open) |
| GitHub | `facebookresearch/audiocraft` (17,000+ stars) |
| Docker | `ashleykleynhans/audiocraft-docker` |
| RunPod | Official RunPod guide + community templates |
| ComfyUI | Yes — custom nodes available |
| Inference speed | ~30s for 30s track on RTX 4090 |

**Strengths:** Most documented, largest ecosystem, most community support, well-integrated into ComfyUI and HuggingFace Inference Endpoints. MIT license is cleanest for commercial use.

**Weaknesses:** 30-120s output limit (not full songs), lower quality than ACE-Step/YuE for complex music.

---

### Stable Audio 3.0 (Stability AI — May 2026)

| Property | Details |
|---|---|
| Parameters | Small (1B), Medium (1.5B), Large (2.7B — API only) |
| VRAM | Small: CPU-capable; Medium: ~12–14.5GB |
| Max length | Up to 380 seconds (~6 minutes) |
| License | Community (free <$1M revenue); Enterprise above |
| GitHub | `Stability-AI/stable-audio-tools` |
| Docker | `ashleykleynhans/stable-audio-tools-docker` |
| RunPod | Community templates available |
| ComfyUI | Yes — official ComfyUI partner (Stable Audio 2.5+) |
| Inference speed | 95s of stereo audio in 8s on A100 |

**Strengths:** Trained on fully licensed data (important for commercial use), longest output duration, very low VRAM for medium model, excellent ComfyUI integration.

**Weaknesses:** Restrictive license above $1M revenue; Large model weights are API-only.

---

### HeartMuLa (2025–2026)

| Property | Details |
|---|---|
| Parameters | 4B (family) |
| VRAM | 24GB (3B variant); 10GB+ with optimization |
| Max length | Full songs |
| License | **Apache 2.0** |
| GitHub | `HeartMuLa/heartlib` |
| Docker | `fspecii/HeartMuLa-Studio` (docker-compose available) |
| ComfyUI | `filliptm/ComfyUI_FL-HeartMuLa` |

**Strengths:** Suno-like interface, reference audio style transfer, multi-language support. Apache 2.0 commercial license.

**Weaknesses:** Newer and less community-tested than AudioCraft/YuE.

---

## Sound Effect Generation Models

### AudioGen (Meta AudioCraft)

| Property | Details |
|---|---|
| VRAM | Small: 4GB / Medium: 8GB / Large: 16GB |
| Max length | 10+ seconds |
| License | **MIT** |
| Docker | Same as MusicGen (`ashleykleynhans/audiocraft-docker` or `tts-webui-docker`) |
| ComfyUI | Yes |
| MCP server | `peerjakobsen/audiogen-mcp` |

Best general-purpose SFX model. MIT license, well-documented, easy to co-deploy with MusicGen in the same container.

---

### Stable Audio Open — SFX Variant

| Property | Details |
|---|---|
| Parameters | 433M (SFX-optimized small) |
| VRAM | CPU-capable; minimal GPU needed |
| License | Community (free <$1M revenue) |
| Docker | `ashleykleynhans/stable-audio-tools-docker` |
| ComfyUI | Yes |

Optimized for drum beats, foley, ambience, instrument riffs. Lowest footprint of any model listed here. Trained on fully licensed data.

---

### FoleyCrafter (Video-to-SFX)

| Property | Details |
|---|---|
| Purpose | Silent video → synchronized sound effects |
| License | Open source (verify repo) |
| ComfyUI | `smthemex/ComfyUI_FoleyCrafter` |
| HuggingFace | Space: `Gyufyjk/FoleyCrafter` |

Only relevant if the use case involves syncing SFX to video (foley work). Not a text-to-audio model.

---

## Docker Images Reference

| Image | Models | Notes |
|---|---|---|
| `ashleykleynhans/tts-webui-docker` | AudioGen, MusicGen, Bark, Tortoise, RVC, Vocos, Demucs | Most complete unified audio container |
| `ashleykleynhans/audiocraft-docker` | MusicGen, AudioGen | Focused AudioCraft; Ubuntu 22.04, CUDA 12.1 |
| `ashleykleynhans/stable-audio-tools-docker` | Stable Audio Open | Stable Audio tooling |
| `olilanz/ai-yue-gp` | YuE | Full-song generation |
| `ghcr.io/dotnetautor/ace-step-1.5-docker:latest` | ACE-Step 1.5 | Configurable VRAM settings |
| `fspecii/HeartMuLa-Studio` | HeartMuLa | docker-compose available |

All community images; none are official vendor Docker images.

---

## ComfyUI Audio Nodes

If building a ComfyUI-based workflow (consistent with the video generation stack):

| Node | Model | Repo |
|---|---|---|
| Stable Audio 2.5 | Stable Audio | Official ComfyUI partner |
| `ComfyUI-StableAudioX` | Stable Audio | `lum3on/ComfyUI-StableAudioX` |
| `ComfyUI-audio` | General audio tools | `eigenpunk/ComfyUI-audio` |
| `ComfyUI_FoleyCrafter` | FoleyCrafter | `smthemex/ComfyUI_FoleyCrafter` |
| `ComfyUI_FL-HeartMuLa` | HeartMuLa | `filliptm/ComfyUI_FL-HeartMuLa` |
| ACE-Step nodes | ACE-Step 1.5 | Official (May 2026) |

---

## VRAM Requirements vs GPU Options

```
Model                        VRAM    A5000 (24GB)  A6000 (48GB)
─────────────────────────────────────────────────────────────────
ACE-Step 1.5 XL (no offload)  20GB  ✅ (4GB spare)  ✅
ACE-Step 1.5 XL (quantized)   12GB  ✅              ✅
YuE 7B fp16                   16GB  ✅              ✅
MusicGen Large                16GB  ✅              ✅
Stable Audio Medium           14GB  ✅              ✅
AudioGen Large                16GB  ✅              ✅

Multi-model (MusicGen + AudioGen)  32GB  ❌         ✅
Multi-model (all four above)       66GB  ❌         ❌  → A100 SXM needed
```

For most use cases, the **RTX A5000 (24GB)** runs any single model comfortably. ACE-Step 1.5 XL fits with only 4GB to spare — use quantized/offload mode to be safe.

---

## License Comparison

| Model | License | Commercial? | Training data licensed? |
|---|---|---|---|
| MusicGen / AudioGen | MIT | Yes, unrestricted | Not guaranteed |
| YuE | Apache 2.0 | Yes, unrestricted | Not guaranteed |
| ACE-Step 1.5 | Apache 2.0 | Yes, unrestricted | Not guaranteed |
| HeartMuLa | Apache 2.0 | Yes, unrestricted | Not guaranteed |
| Stable Audio 3.0 | Community/Enterprise | Free <$1M revenue | **Yes — fully licensed** |
| FoleyCrafter | Open (verify) | Likely yes | Research data |

**Note:** If output audio will be used in commercial products and training data provenance matters, Stable Audio (Stability AI) is the only model with fully licensed training data.

---

## Recommendation by Use Case

| Use case | Model | Container |
|---|---|---|
| Full songs, best quality | ACE-Step 1.5 XL | `ghcr.io/dotnetautor/ace-step-1.5-docker` |
| Full songs, lyrics-driven | YuE | `olilanz/ai-yue-gp` |
| Short clips, best ecosystem | MusicGen Large | `ashleykleynhans/audiocraft-docker` |
| SFX, general purpose | AudioGen Large | `ashleykleynhans/tts-webui-docker` |
| SFX, licensed training data | Stable Audio Open SFX | `ashleykleynhans/stable-audio-tools-docker` |
| Video-to-SFX (foley) | FoleyCrafter | ComfyUI node |
| ComfyUI workflow integration | Stable Audio 2.5 + ACE-Step | ComfyUI custom image |
| Everything in one container | All AudioCraft models | `ashleykleynhans/tts-webui-docker` |
