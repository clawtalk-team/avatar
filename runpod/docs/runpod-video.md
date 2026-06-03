# Spec: Deploy Wan 2.2 Video Generation on RunPod (RTX PRO 6000 Blackwell)

## Purpose
Deploy a self-hosted, open-source text-to-video and image-to-video generation
service using **Wan 2.2** (Alibaba, MoE diffusion, ~27B total / ~14B active
params) served through **ComfyUI** on a single RunPod **RTX PRO 6000 Blackwell**
GPU (96 GB GDDR7 VRAM). The end state is a running ComfyUI instance reachable in
a browser on port 8188, with Wan 2.2 14B weights loaded and a working T2V and
I2V workflow.

## Target environment (assumptions)
- Provider: RunPod, GPU Cloud (pod, not serverless).
- GPU: 1x RTX PRO 6000 Blackwell, 96 GB VRAM. (VRAM is not a constraint; run
  full fp16/fp8 14B weights, no aggressive offloading needed.)
- CUDA: 12.8 base image.
- Persistent storage: a RunPod Network Volume of >= 100 GB mounted at
  `/workspace` so model weights survive pod restarts. Weights are large
  (tens of GB); do NOT store them on the ephemeral container disk.
- OS user has sudo/root inside the pod (standard for RunPod).
- Python 3.10+ available in the base image.

## Hard constraints / agent guardrails
- The agent must NOT enter any credentials, payment details, or API keys into
  web forms on the operator's behalf. If a HuggingFace token is needed for a
  gated download, the agent must PAUSE and ask the operator to provide it as an
  environment variable, not hardcode it.
- The agent must NOT publish, expose publicly, or change sharing/network
  settings beyond the documented port 8188 exposure that RunPod provides by
  default.
- Model licenses vary. Wan 2.2 is Apache 2.0, but the agent must surface the
  license of any additional LoRA/checkpoint it downloads and not assume
  commercial-use rights.
- All large downloads happen onto the network volume (`/workspace`), never the
  container root filesystem.
- The agent must verify each step's success (process running, file exists,
  port listening) before proceeding to the next.

---

## Decision point: template vs. manual install
There are two valid implementation paths. The agent should pick based on the
operator's preference; default to **Path A** for reliability.

- **Path A — Pre-built RunPod template (recommended).** Use a community
  one-click Wan 2.1/2.2 ComfyUI template (CUDA 12.8). Fastest, least
  error-prone. Startup/provisioning takes ~5–20 minutes.
- **Path B — Manual install on a clean PyTorch pod.** Full control over
  versions and workflow. Use only if the operator wants a reproducible script
  or the templates are unavailable.

---

## Path A: Pre-built template

### A1. Provision the pod
1. In RunPod, create a Network Volume >= 100 GB in the target region. Note the
   region — the pod must be deployed in the **same region** as the volume.
2. Deploy a new Pod. Select GPU: RTX PRO 6000 Blackwell (96 GB).
3. Choose a CUDA 12.8 Wan 2.1/2.2 ComfyUI community template (e.g. a
   "One-Click ComfyUI - Wan 2.1 / Wan 2.2 (CUDA 12.8)" type template). These
   are purpose-built and load ComfyUI without manual setup.
4. Attach the network volume (mount at `/workspace`).
5. Before deploying, open **Edit Template → Environment Variables** and set the
   variable that triggers the Wan 2.2 weight download to `true` (commonly named
   `download_WAN_2.2` or similar — read the template's own variable names; the
   exact key depends on the template). Set Overrides.
   - This is REQUIRED. If skipped, the 2.2 weights are not downloaded and the
     workflow will not run.
6. Deploy.

### A2. Wait for provisioning
- Watch the **Logs** tab (System + Container logs). Provisioning typically
  takes 5–20 minutes (occasionally up to ~15 min just for install).
- Wait until the log reports ComfyUI is up and the service shows "ready."

### A3. Connect
- Click **Connect** on the pod → open port **8188** → ComfyUI opens in a new
  browser tab.

### A4. Load a workflow and test
- Open a Wan 2.2 T2V workflow from the Workflows menu (templates ship with
  starter workflows for T2V / I2V).
- Run the workflow with a simple test prompt to confirm end-to-end generation.
- Then test an I2V workflow with a sample input image.

Proceed to **Validation** below.

---

## Path B: Manual install (clean PyTorch + CUDA 12.8 pod)

Run these inside the pod's web terminal / SSH. All paths target the network
volume at `/workspace`.

### B1. Base ComfyUI install
```bash
cd /workspace
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### B2. Install ComfyUI Manager (for node/dependency management)
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
cd ComfyUI-Manager
pip install -r requirements.txt
cd /workspace/ComfyUI
```

### B3. Download Wan 2.2 weights
- Use the ComfyUI-repackaged Wan 2.2 files from the `Comfy-Org` HuggingFace
  repo (`Comfy-Org/Wan_2.2_ComfyUI_Repackaged`). On a 96 GB card, prefer the
  full 14B high-noise + low-noise expert weights at fp16 (or fp8 to save disk).
- File categories and their destination directories under
  `/workspace/ComfyUI/models/`:
  - diffusion/UNet experts → `diffusion_models/` (or `unet/` per workflow)
  - text encoder → `text_encoders/`
  - VAE → `vae/`
  - optional 4-step speed LoRAs → `loras/`
- Example (LoRA, illustrative — confirm current filenames against the repo
  before running, names change between point releases):
```bash
cd /workspace/ComfyUI/models/loras
wget -O wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"
```
- If any file is gated, the agent must PAUSE and request a HuggingFace token
  from the operator, then export it as `HF_TOKEN` / `HUGGINGFACE_TOKEN` — do
  not hardcode it into scripts.

### B4. Launch ComfyUI
```bash
cd /workspace/ComfyUI
nohup python main.py --listen 0.0.0.0 --port 8188 > /workspace/comfyui.log 2>&1 &
tail -f /workspace/comfyui.log   # Ctrl+C stops viewing, not the server
```
- Confirm in RunPod the pod exposes HTTP port 8188; Connect → port 8188.

### B5. Load workflow
- Import a Wan 2.2 T2V workflow JSON (community starter workflows exist; the
  agent can fetch a known-good one or build the standard MoE two-sampler graph:
  high-noise expert for layout → low-noise expert for refinement → VAE decode →
  video combine).
- Run a test generation.

---

## Recommended generation settings (starting point)
- Model variant: Wan2.2-T2V-A14B (text-to-video) and Wan2.2-I2V-A14B
  (image-to-video).
- Precision: fp16 (96 GB has ample headroom) or fp8 to cut disk/VRAM.
- Resolution: start 1280x720 (720p). The card can handle 720p comfortably;
  push higher only after a baseline works.
- Frames: start ~81 frames (~5 s clip) for first tests.
- CFG / guidance: ~3.5 as a starting value; raise for closer prompt adherence
  at the risk of over-processing.
- Steps: full sampler steps for quality, OR use the 4-step lightx2v LoRAs for
  fast iteration during prototyping.

---

## Validation checklist (agent must confirm all)
1. Pod is in the same region as the network volume; volume mounted at
   `/workspace`.
2. `nvidia-smi` shows the RTX PRO 6000 with ~96 GB and the driver loaded.
3. ComfyUI process is listening on 0.0.0.0:8188 (`curl -sf http://localhost:8188`
   returns 200, or the UI loads in the browser).
4. Wan 2.2 weight files exist on disk under `/workspace/ComfyUI/models/...`
   with non-zero, expected sizes.
5. A T2V test prompt produces a playable video file in
   `/workspace/ComfyUI/output/`.
6. An I2V test with a sample image produces a playable video.
7. License note recorded for every downloaded artifact.

## Cost / operational notes
- Stop the pod when not generating — billing is per-hour while running.
- Keep weights on the network volume so a stopped/restarted pod doesn't
  re-download tens of GB.
- The RTX PRO 6000 Blackwell lacks NVLink; irrelevant for single-GPU here, but
  note it if scaling to multi-GPU later.

## Deliverable
A reproducible setup (template config OR the B1–B4 shell script committed to a
repo) plus the validated workflow JSON files for T2V and I2V, and a short
README capturing: the exact model filenames/versions used, the env vars
required, and the launch command.
