#!/usr/bin/env python3
"""
generate_starvector_from_images.py
------------------------------------
Run StarVector im2svg on pre-generated face PNGs (e.g. from flashimage_generate.py)
on a RunPod GPU pod, then save the resulting SVGs as a head set compatible with
the webapp and generate_head.py gallery format.

Workflow:
  1. Read PNG files from --input-dir (default: outputs/flashimage/)
  2. Start a RunPod GPU pod
  3. Upload PNGs + run StarVector 8B im2svg on each
  4. Download SVGs → outputs/heads/<name>/
  5. Write gallery.html
  6. Stop pod

Usage:
  # Default: use outputs/flashimage/ images, name from directory
  python runpod/generate_starvector_from_images.py --name gemini_woman

  # Custom image dir
  python runpod/generate_starvector_from_images.py \\
      --input-dir outputs/flashimage/ \\
      --name gemini_woman \\
      --keep-pod

  # Smaller 1B model (faster, lower VRAM)
  python runpod/generate_starvector_from_images.py --name gemini_woman --model 1b

Environment (set in .env):
  RUNPOD_API_KEY    RunPod API key
  HF_TOKEN          HuggingFace token
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"

DOCKER_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"

# 24+ GB VRAM for 8B model; 1B model fits on 16 GB cards too
GPU_TYPES_8B = [
    # 80GB+ cards
    "NVIDIA A100 80GB PCIe",
    "NVIDIA A100-SXM4-80GB",
    "NVIDIA H100 80GB HBM3",
    "NVIDIA H100 PCIe",
    "NVIDIA H100 NVL",
    "NVIDIA H200",
    "NVIDIA B200",
    # 48GB cards
    "NVIDIA RTX A6000",
    "NVIDIA L40S",
    "NVIDIA L40",
    "NVIDIA RTX 6000 Ada Generation",
    "NVIDIA A40",
    # 40GB cards
    "NVIDIA A100-SXM4-40GB",
    # 32GB cards (should fit 8B in fp16)
    "NVIDIA GeForce RTX 5090",
    "NVIDIA RTX 5000 Ada",
    # 96GB Blackwell cards
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
    "NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition",
]
GPU_TYPES_1B = [
    # 24GB cards (comfortable for 1B fp16)
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 3090 Ti",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA L4",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A4000",
    "NVIDIA GeForce RTX 5090",
] + GPU_TYPES_8B

CLOUD_TYPES = ["SECURE", "COMMUNITY"]
SSH_TIMEOUT = 300
SSH_INTERVAL = 10

# All 15 OVR viseme names we expect from flashimage_generate.py
VISEME_NAMES = ["sil", "PP", "FF", "TH", "DD", "kk", "CH", "SS", "nn", "RR", "aa", "E", "I", "O", "U"]

REMOTE_SCRIPT = r'''#!/usr/bin/env python3
"""Run StarVector im2svg on uploaded PNG frames. Executed on the RunPod pod."""

import os, sys, time, json, glob
import torch
from PIL import Image
from pathlib import Path

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = os.environ.get("STARVECTOR_MODEL", "starvector/starvector-8b-im2svg")
IN_DIR  = Path("/workspace/input_images")
OUT_DIR = Path("/workspace/svg_out")
OUT_DIR.mkdir(exist_ok=True)

print(f"Device  : {DEVICE}")
print(f"Model   : {MODEL_ID}")

from starvector.model.starvector_arch import StarVectorForCausalLM

print("Loading model (may take a few minutes on first run)...")
model = StarVectorForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    trust_remote_code=True,
    token=os.environ.get("HF_TOKEN"),
)
model.to(DEVICE)
model.eval()
print("Model loaded.\n")

png_files = sorted(IN_DIR.glob("*.png"))
print(f"Input files ({len(png_files)}): {[f.name for f in png_files]}")

results = []
for png_path in png_files:
    stem = png_path.stem          # e.g. "sil", "aa", "O"
    print(f"[{stem:4s}]  {png_path.name}  ...", end=" ", flush=True)

    img = Image.open(png_path).convert("RGB")
    # StarVector expects 224x224 input
    img_resized = img.resize((224, 224), Image.LANCZOS)

    processor = model.model.processor
    pixel_values = processor(img_resized, return_tensors="pt")["pixel_values"]
    if pixel_values.dim() == 3:
        pixel_values = pixel_values.unsqueeze(0)
    pixel_values = pixel_values.to(DEVICE, dtype=torch.float16)

    t0 = time.time()
    try:
        with torch.no_grad():
            raw_svg = model.generate_im2svg({"image": pixel_values}, max_length=8000)[0]
        elapsed = time.time() - t0
        out_path = OUT_DIR / f"{stem}.svg"
        out_path.write_text(raw_svg)
        char_count = len(raw_svg)
        print(f"OK  ({char_count:,} chars, {elapsed:.1f}s)")
        results.append({"viseme": stem, "elapsed": elapsed, "svg_len": char_count, "status": "ok"})
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILED ({elapsed:.1f}s): {e}")
        results.append({"viseme": stem, "status": "failed", "error": str(e)})

print(f"\nDone. {sum(1 for r in results if r['status']=='ok')}/{len(results)} succeeded.")
print(json.dumps(results))
print("COMPLETE")
'''


# ── env helpers ───────────────────────────────────────────────────────────────

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
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v


def graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    import urllib.request, urllib.error
    payload = json.dumps({"query": query, **({"variables": variables} if variables else {})}).encode()
    req = urllib.request.Request(
        RUNPOD_GRAPHQL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "errors" in body:
        raise RuntimeError(f"RunPod GraphQL errors: {body['errors']}")
    return body["data"]


# ── pod lifecycle ─────────────────────────────────────────────────────────────

def stop_pod(api_key: str, pod_id: str):
    print(f"Stopping pod {pod_id}...")
    try:
        graphql(api_key, """
            mutation($podId: String!) { podStop(input: {podId: $podId}) { id desiredStatus } }
        """, {"podId": pod_id})
        print(f"  Pod {pod_id} stop requested.")
    except Exception as e:
        print(f"  Warning: {e}")


def create_pod(api_key: str, gpu_list: list[str]) -> tuple[str, str]:
    for cloud_type in CLOUD_TYPES:
        print(f"\nTrying cloud: {cloud_type}")
        for gpu_type in gpu_list:
            print(f"  GPU: {gpu_type}")
            try:
                data = graphql(api_key, """
                    mutation($input: PodFindAndDeployOnDemandInput!) {
                        podFindAndDeployOnDemand(input: $input) {
                            id desiredStatus
                            runtime { ports { ip isIpPublic privatePort publicPort type } }
                        }
                    }
                """, {"input": {
                    "name": "starvector-im2svg",
                    "imageName": DOCKER_IMAGE,
                    "gpuTypeId": gpu_type,
                    "cloudType": cloud_type,
                    "startSsh": True,
                    "ports": "22/tcp",
                    "containerDiskInGb": 40,
                    "volumeInGb": 0,
                    "minVcpuCount": 4,
                    "minMemoryInGb": 24,
                }})
                pod = data["podFindAndDeployOnDemand"]
                pod_id = pod["id"]
                ssh_host = f"{pod_id}-22.proxy.runpod.net"
                print(f"Pod created: {pod_id}  ({cloud_type} / {gpu_type})")
                return pod_id, ssh_host
            except RuntimeError as e:
                if any(x in str(e) for x in ("SUPPLY_CONSTRAINT", "OUT_OF_CAPACITY", "no available")):
                    print(f"    No capacity, trying next...")
                    continue
                raise
    raise RuntimeError(f"Could not find available GPU")


def wait_for_ssh(ssh_host: str, timeout: int = SSH_TIMEOUT) -> bool:
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
        print(f"  {elapsed}s — not ready, retrying in {SSH_INTERVAL}s...")
        time.sleep(SSH_INTERVAL)
    return False


def ssh_run(ssh_host: str, cmd: str, check: bool = True):
    return subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ssh_host}", cmd],
        text=True, check=check
    )


def scp_to(ssh_host: str, local: str, remote: str):
    subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", local, f"root@{ssh_host}:{remote}"], check=True)


def scp_dir_to(ssh_host: str, local_dir: str, remote_dir: str):
    """Upload all PNGs in local_dir to remote_dir."""
    subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", "-r", local_dir, f"root@{ssh_host}:{remote_dir}"],
        check=True
    )


def scp_from(ssh_host: str, remote: str, local: str):
    subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-r", f"root@{ssh_host}:{remote}", local], check=True)


# ── gallery ───────────────────────────────────────────────────────────────────

VISEME_PHONEMES = {
    "sil": "silence", "PP": "p, b, m", "FF": "f, v", "TH": "th, dh",
    "DD": "t, d", "kk": "k, g", "CH": "ch, j, sh, zh", "SS": "s, z",
    "nn": "n, l, ng", "RR": "r", "aa": "ah, aa, ae", "E": "eh, ey",
    "I": "ih, iy", "O": "oh, ao, ow", "U": "oo, uw, uh",
}


def write_gallery(out_dir: Path, name: str, input_dir: Path | None = None):
    cards = []
    for v in VISEME_NAMES:
        svg_file = out_dir / f"{v}.svg"
        png_file = (input_dir / f"{v}.png") if input_dir else None

        if not svg_file.exists():
            cards.append(f'<div class="card"><div class="label">{v}</div><p style="color:#f66">missing</p></div>')
            continue

        svg_content = svg_file.read_text()
        phonemes = VISEME_PHONEMES.get(v, "")
        png_tag = ""
        if png_file and png_file.exists():
            import base64
            png_b64 = base64.b64encode(png_file.read_bytes()).decode()
            png_tag = f'<div class="label">Gemini input</div><img src="data:image/png;base64,{png_b64}" style="width:100px;height:100px;border-radius:6px;margin-bottom:6px"/>'

        cards.append(f"""
      <div class="card">
        <div class="label">{v} — {phonemes}</div>
        {png_tag}
        <div class="label">StarVector SVG</div>
        <div class="svg-wrap">{svg_content}</div>
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>{name} — StarVector Gallery</title>
<style>
  body{{background:#1a1a1a;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
  h1{{color:#fff;margin-bottom:4px}}
  p.sub{{color:#888;margin-top:0;margin-bottom:20px;font-size:14px}}
  .grid{{display:flex;flex-wrap:wrap;gap:20px}}
  .card{{background:#2a2a2a;border-radius:12px;padding:12px;text-align:center;width:240px}}
  .label{{font-size:12px;color:#aaa;margin:0 0 8px}}
  .svg-wrap svg{{width:200px;height:200px;display:block;margin:0 auto}}
</style></head>
<body>
  <h1>{name} — StarVector im2svg</h1>
  <p class="sub">Pipeline: Gemini 2.5 Flash Image (OpenRouter) → StarVector 8B im2svg (RunPod)</p>
  <div class="grid">{"".join(cards)}</div>
</body></html>"""

    gallery = out_dir / "gallery.html"
    gallery.write_text(html)
    return gallery


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="StarVector im2svg on Gemini-generated face images")
    parser.add_argument("--input-dir", default="outputs/flashimage",
                        help="Dir containing <viseme>.png files (default: outputs/flashimage)")
    parser.add_argument("--name", default="gemini_woman",
                        help="Output head name (creates outputs/heads/<name>/)")
    parser.add_argument("--model", choices=["1b", "8b"], default="8b",
                        help="StarVector model size (default: 8b)")
    parser.add_argument("--visemes", nargs="+", default=VISEME_NAMES,
                        help="Subset of visemes to process (default: all 15)")
    parser.add_argument("--keep-pod", action="store_true",
                        help="Leave pod running after completion")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not api_key:
        sys.exit("Error: RUNPOD_API_KEY not set")

    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        hf_path = Path.home() / ".cache" / "huggingface" / "token"
        if hf_path.exists():
            hf_token = hf_path.read_text().strip()
    if not hf_token:
        sys.exit("Error: HF_TOKEN not set")

    input_dir = REPO_ROOT / args.input_dir
    if not input_dir.exists():
        sys.exit(f"Input directory not found: {input_dir}\nRun scripts/flashimage_generate.py first")

    # Find which PNG files are available
    available = {f.stem: f for f in input_dir.glob("*.png")}
    missing = [v for v in args.visemes if v not in available]
    if missing:
        print(f"Warning: no PNG for visemes: {missing}")
        print(f"  Run: python scripts/flashimage_generate.py {' '.join(missing)}")
    to_process = [v for v in args.visemes if v in available]
    if not to_process:
        sys.exit("No input images found. Run flashimage_generate.py first.")

    print(f"Processing {len(to_process)} visemes: {to_process}")

    out_dir = REPO_ROOT / "outputs" / "heads" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check for already-done SVGs
    skip = [v for v in to_process if (out_dir / f"{v}.svg").exists()]
    todo = [v for v in to_process if v not in skip]
    if skip:
        print(f"Skipping {len(skip)} already done: {skip}")
    if not todo:
        print("All SVGs already exist — writing gallery only.")
        gallery = write_gallery(out_dir, args.name, input_dir)
        print(f"Gallery: {gallery}")
        import subprocess as sp
        sp.run(["open", str(gallery)], check=False)
        return

    model_id = f"starvector/starvector-{'1b' if args.model == '1b' else '8b'}-im2svg"
    gpu_list = GPU_TYPES_1B if args.model == "1b" else GPU_TYPES_8B

    print(f"\nModel: {model_id}")
    print(f"Output: {out_dir}")

    pod_id, ssh_host = create_pod(api_key, gpu_list)

    try:
        if not wait_for_ssh(ssh_host):
            sys.exit(f"Timed out waiting for SSH on {ssh_host}")

        # Create remote input directory and upload PNGs
        print("\nUploading images...")
        ssh_run(ssh_host, "mkdir -p /workspace/input_images")
        for v in todo:
            scp_to(ssh_host, str(available[v]), f"/workspace/input_images/{v}.png")
        print(f"Uploaded {len(todo)} PNGs.")

        # Upload run script
        tmp_script = out_dir / "_remote_im2svg.py"
        tmp_script.write_text(REMOTE_SCRIPT)
        scp_to(ssh_host, str(tmp_script), "/workspace/im2svg_run.py")
        tmp_script.unlink()

        # Install dependencies
        print("\nInstalling StarVector (3-5 min)...")
        ssh_run(ssh_host,
            "pip install -q --upgrade-strategy only-if-needed "
            "transformers==4.49.0 tokenizers==0.21.1 sentencepiece accelerate "
            "pillow omegaconf fairscale scikit-learn numpy"
        )
        ssh_run(ssh_host,
            "pip install -q --no-deps git+https://github.com/joanrod/star-vector.git"
        )
        print("Dependencies installed.")

        # Run generation
        print(f"\nRunning StarVector im2svg on {len(todo)} images...")
        ssh_run(ssh_host,
            f"HF_TOKEN={hf_token} STARVECTOR_MODEL={model_id} python /workspace/im2svg_run.py"
        )

        # Download SVGs
        print("\nDownloading SVGs...")
        ssh_run(ssh_host, "ls /workspace/svg_out/", check=False)  # show what's there
        scp_from(ssh_host, "/workspace/svg_out/*.svg", str(out_dir))
        print(f"SVGs saved to {out_dir}")

    finally:
        if not args.keep_pod:
            stop_pod(api_key, pod_id)
        else:
            print(f"\nPod left running: root@{ssh_host}  (id: {pod_id})")

    # Copy existing SVGs that were skipped (already present)
    svg_count = len(list(out_dir.glob("*.svg")))
    print(f"\nTotal SVGs in {out_dir}: {svg_count}")

    gallery = write_gallery(out_dir, args.name, input_dir)
    print(f"Gallery: {gallery}")

    import subprocess as sp
    sp.run(["open", str(gallery)], check=False)


if __name__ == "__main__":
    main()
