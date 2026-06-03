#!/usr/bin/env python3
"""
Generate SVG cartoon faces using StarVector on a RunPod GPU pod.

Workflow:
  1. Stop any existing pod listed in .env (RUNPOD_POD_ID)
  2. Create a fresh GPU pod with PyTorch + SSH
  3. Wait for SSH to become reachable
  4. Upload svg_generator.py + generation script
  5. pip-install StarVector deps on the pod (no flash_attn — CUDA-optional)
  6. Run im2svg for TARGET_VISEMES
  7. Download the PNG inputs and SVG outputs
  8. Write a local gallery.html
  9. Stop (not terminate) the pod so weights cache on the network volume

Usage:
    python runpod/generate_starvector.py
    python runpod/generate_starvector.py --keep-pod   # leave pod running after

Environment variables (set in .env at project root, or export):
    RUNPOD_API_KEY   – RunPod API key
    RUNPOD_POD_ID    – Existing pod to stop before starting new one (optional)
    HF_TOKEN         – HuggingFace token (needed for bigcode/starcoderbase-1b)

Outputs:
    outputs/starvector/<viseme>_input.png   rasterised input
    outputs/starvector/<viseme>_output.svg  StarVector SVG output
    outputs/starvector/gallery.html         side-by-side comparison
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "starvector"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"

# ── pod config ────────────────────────────────────────────────────────────────

# PyTorch 2.1 with CUDA 11.8  — small, widely available on RunPod
DOCKER_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"

# GPU preference order — any 24 GB+ card handles StarVector 1B in fp16
GPU_TYPES = [
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA L4",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A4000",
    "NVIDIA A40",
    "NVIDIA RTX A6000",
    "NVIDIA L40S",
    "NVIDIA GeForce RTX 3090 Ti",
    "NVIDIA RTX 6000 Ada Generation",
]

# Try SECURE first, fall back to COMMUNITY if no capacity anywhere
CLOUD_TYPES = ["SECURE", "COMMUNITY"]

SSH_TIMEOUT = 300   # seconds to wait for SSH to become available
SSH_INTERVAL = 10

TARGET_VISEMES = ["sil", "PP", "aa", "O", "U", "I", "FF", "CH"]

# ── remote generation script (uploaded + executed on pod) ────────────────────

REMOTE_SCRIPT = '''#!/usr/bin/env python3
"""Run StarVector im2svg on cartoon face PNGs. Executed on the RunPod pod."""

import os, sys, io, time, json
import torch
import cairosvg
from PIL import Image
from pathlib import Path

sys.path.insert(0, "/workspace")  # svg_generator lives here after upload
from svg_generator import build_face_svg, VISEMES

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = "starvector/starvector-1b-im2svg"
OUT = Path("/workspace/starvector_out")
OUT.mkdir(exist_ok=True)

TARGET_VISEMES = {target}

print(f"Device: {{DEVICE}}")
print(f"Visemes: {{TARGET_VISEMES}}")

from starvector.model.starvector_arch import StarVectorForCausalLM

print("Loading model...")
model = StarVectorForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    trust_remote_code=True,
    token=os.environ.get("HF_TOKEN"),
)
model.to(DEVICE)
model.eval()
print("Model loaded.\\n")

results = []
for viseme_name in TARGET_VISEMES:
    if viseme_name not in VISEMES:
        print(f"  [skip] {{viseme_name}} not in VISEMES")
        continue

    jaw, spread, part = VISEMES[viseme_name]["shape"]
    print(f"[{{viseme_name:4s}}]  jaw={{jaw:.2f}}  spread={{spread:+.2f}}  part={{part:+.2f}}")

    svg_str = build_face_svg(viseme_name, jaw, spread, part)
    png_bytes = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=224, output_height=224)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    input_path = OUT / f"{{viseme_name}}_input.png"
    img.save(input_path)
    print(f"  input: {{input_path.name}}")

    processor = model.model.processor
    pixel_values = processor(img, return_tensors="pt")["pixel_values"]
    if pixel_values.dim() == 3:
        pixel_values = pixel_values.unsqueeze(0)
    pixel_values = pixel_values.to(DEVICE, dtype=torch.float16)

    t0 = time.time()
    try:
        with torch.no_grad():
            raw_svg = model.generate_im2svg({{"image": pixel_values}}, max_length=4000)[0]
        elapsed = time.time() - t0
        output_path = OUT / f"{{viseme_name}}_output.svg"
        output_path.write_text(raw_svg)
        print(f"  output: {{output_path.name}}  ({{len(raw_svg):,}} chars, {{elapsed:.1f}}s)\\n")
        results.append({{"viseme": viseme_name, "elapsed": elapsed, "svg_len": len(raw_svg)}})
    except Exception as e:
        print(f"  generation failed: {{e}}")

print(json.dumps(results))
print("DONE")
'''

# ── env / API helpers ─────────────────────────────────────────────────────────

def load_dotenv():
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v


def graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        RUNPOD_GRAPHQL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "errors" in body:
        raise RuntimeError(f"RunPod GraphQL errors: {body['errors']}")
    return body["data"]


# ── pod lifecycle ─────────────────────────────────────────────────────────────

def stop_pod(api_key: str, pod_id: str):
    """Stop (not terminate) an existing pod."""
    print(f"Stopping existing pod {pod_id}...")
    try:
        data = graphql(api_key, """
            query($podId: String!) {
                pod(input: { podId: $podId }) { id desiredStatus }
            }
        """, {"podId": pod_id})
        status = data["pod"]["desiredStatus"]
        if status == "EXITED":
            print(f"  Pod {pod_id} already stopped.")
            return
        graphql(api_key, """
            mutation($podId: String!) {
                podStop(input: { podId: $podId }) { id desiredStatus }
            }
        """, {"podId": pod_id})
        print(f"  Pod {pod_id} stop requested.")
    except Exception as e:
        print(f"  Warning: could not stop pod {pod_id}: {e}")


def create_pod(api_key: str) -> tuple[str, str]:
    """
    Create a new on-demand GPU pod with SSH enabled.
    Returns (pod_id, ssh_host).
    """
    for cloud_type in CLOUD_TYPES:
        print(f"\nTrying cloud: {cloud_type}")
        for gpu_type in GPU_TYPES:
            print(f"  GPU: {gpu_type}")
            try:
                data = graphql(api_key, """
                    mutation($input: PodFindAndDeployOnDemandInput!) {
                        podFindAndDeployOnDemand(input: $input) {
                            id
                            desiredStatus
                            runtime {
                                uptimeInSeconds
                                ports { ip isIpPublic privatePort publicPort type }
                            }
                        }
                    }
                """, {
                    "input": {
                        "name": "starvector-gen",
                        "imageName": DOCKER_IMAGE,
                        "gpuTypeId": gpu_type,
                        "cloudType": cloud_type,
                        "startSsh": True,
                        "ports": "22/tcp",
                        "containerDiskInGb": 30,
                        "volumeInGb": 0,
                        "minVcpuCount": 4,
                        "minMemoryInGb": 16,
                    }
                })
                pod = data["podFindAndDeployOnDemand"]
                pod_id = pod["id"]
                ssh_host = f"{pod_id}-22.proxy.runpod.net"
                print(f"Pod created: {pod_id}  ({cloud_type} / {gpu_type})")
                print(f"SSH: root@{ssh_host}")
                return pod_id, ssh_host
            except RuntimeError as e:
                err = str(e)
                if any(x in err for x in ("SUPPLY_CONSTRAINT", "OUT_OF_CAPACITY", "no available", "no longer any")):
                    print(f"    No capacity, trying next...")
                    continue
                raise
    raise RuntimeError(f"Could not find available GPU (tried {CLOUD_TYPES} × {GPU_TYPES})")


def wait_for_ssh(ssh_host: str, timeout: int = SSH_TIMEOUT) -> bool:
    """Poll until SSH is reachable. Returns True on success."""
    print(f"Waiting for SSH on {ssh_host}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", f"root@{ssh_host}", "echo ok"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and "ok" in result.stdout:
            print("SSH ready.")
            return True
        elapsed = int(time.time() - (deadline - timeout))
        print(f"  {elapsed}s — SSH not ready yet, retrying in {SSH_INTERVAL}s...")
        time.sleep(SSH_INTERVAL)
    return False


def ssh_run(ssh_host: str, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ssh_host}", cmd],
        capture_output=False, text=True, check=check
    )
    return result


def scp_to(ssh_host: str, local: str, remote: str):
    subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", local, f"root@{ssh_host}:{remote}"],
        check=True
    )


def scp_from(ssh_host: str, remote: str, local: str):
    subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", "-r",
         f"root@{ssh_host}:{remote}", local],
        check=True
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate StarVector SVG faces on RunPod")
    parser.add_argument("--keep-pod", action="store_true",
                        help="Leave the pod running after generation (useful for debugging)")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not api_key:
        sys.exit("Error: RUNPOD_API_KEY not set. Add it to .env or export it.")

    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        hf_token_file = Path.home() / ".cache" / "huggingface" / "token"
        if hf_token_file.exists():
            hf_token = hf_token_file.read_text().strip()
    if not hf_token:
        sys.exit("Error: HF_TOKEN not set. Set it in .env or export HF_TOKEN=hf_...")

    # 1. Stop existing pod if configured
    existing_pod_id = os.environ.get("RUNPOD_POD_ID", "").strip()
    if existing_pod_id:
        stop_pod(api_key, existing_pod_id)

    # 2. Create new GPU pod
    pod_id, ssh_host = create_pod(api_key)

    try:
        # 3. Wait for SSH
        if not wait_for_ssh(ssh_host):
            sys.exit(f"Timed out waiting for SSH on {ssh_host}")

        # 4. Upload files
        print("\nUploading files...")
        svg_gen_path = REPO_ROOT / "svg_generator.py"
        scp_to(ssh_host, str(svg_gen_path), "/workspace/svg_generator.py")

        remote_script = REMOTE_SCRIPT.format(target=repr(TARGET_VISEMES))
        tmp_script = OUT_DIR / "_remote_generate.py"
        tmp_script.write_text(remote_script)
        scp_to(ssh_host, str(tmp_script), "/workspace/starvector_generate.py")
        tmp_script.unlink()
        print("Files uploaded.")

        # 5. Install dependencies (skip flash_attn — CUDA-optional, slow to build)
        print("\nInstalling dependencies (this takes ~3-5 minutes)...")
        ssh_run(ssh_host,
            "pip install -q --upgrade-strategy only-if-needed "
            "transformers==4.49.0 tokenizers==0.21.1 sentencepiece accelerate "
            "cairosvg pillow omegaconf fairscale scikit-learn numpy"
        )
        # Install starvector from GitHub (no flash_attn)
        ssh_run(ssh_host,
            "pip install -q --no-deps git+https://github.com/joanrod/star-vector.git"
        )
        print("Dependencies installed.")

        # 6. Run generation
        print(f"\nRunning StarVector im2svg for {TARGET_VISEMES}...")
        ssh_run(ssh_host,
            f"HF_TOKEN={hf_token} python /workspace/starvector_generate.py"
        )

        # 7. Download outputs
        print("\nDownloading outputs...")
        scp_from(ssh_host, "/workspace/starvector_out/*", str(OUT_DIR))
        print(f"Outputs saved to {OUT_DIR}")

        # 8. Write gallery
        write_gallery()

    finally:
        if not args.keep_pod:
            print(f"\nStopping pod {pod_id}...")
            stop_pod(api_key, pod_id)
        else:
            print(f"\nPod left running: root@{ssh_host}")
            print(f"Stop it with: python runpod/pod.py stop  (after adding {pod_id} to .env)")


def write_gallery():
    png_files = sorted(OUT_DIR.glob("*_input.png"))
    if not png_files:
        print("No outputs to gallery.")
        return

    cards = []
    for png in png_files:
        viseme = png.stem.replace("_input", "")
        svg = OUT_DIR / f"{viseme}_output.svg"
        input_rel = png.relative_to(REPO_ROOT)
        if svg.exists():
            output_rel = svg.relative_to(REPO_ROOT)
            output_tag = f'<object type="image/svg+xml" data="../{output_rel}" width="256" height="256"><img src="../{input_rel}" width="256" height="256"/></object>'
        else:
            output_tag = f'<p style="color:#f66">no output</p>'
        cards.append(f"""
      <div class="card">
        <div class="label">{viseme} — input</div>
        <img src="../{input_rel}" width="256" height="256"/>
        <div class="label">StarVector output</div>
        {output_tag}
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
  </style>
</head>
<body>
  <h1>StarVector im2svg — Cartoon Viseme Faces</h1>
  <p style="color:#888">Input: parametric SVG rasterized to 224×224 PNG. Output: StarVector 1B trace.</p>
  <div class="grid">{"".join(cards)}</div>
</body>
</html>"""

    out = OUT_DIR / "gallery.html"
    out.write_text(html)
    import subprocess as sp
    sp.run(["open", str(out)], check=False)
    print(f"Gallery: {out}")


if __name__ == "__main__":
    main()
