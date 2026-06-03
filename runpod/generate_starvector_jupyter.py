#!/usr/bin/env python3
"""
Generate SVG cartoon faces using StarVector via the Jupyter API on the running RunPod pod.

The ComfyUI pod exposes Jupyter on port 8888. We use the Jupyter REST+WebSocket API to:
  1. Upload svg_generator.py and the generation script
  2. Create a Python kernel
  3. Execute the generation code
  4. Download the outputs via the Jupyter contents API

Usage:
    python runpod/generate_starvector_jupyter.py

Environment:
    RUNPOD_API_KEY   – used as Jupyter token (or leave empty if unauthenticated)
    RUNPOD_POD_ID    – pod ID (defaults to REDACTED_POD_ID)
    HF_TOKEN         – HuggingFace token for bigcode/starcoderbase-1b

Outputs:
    outputs/starvector/<viseme>_input.png
    outputs/starvector/<viseme>_output.svg
    outputs/starvector/gallery.html
"""

import asyncio
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import websockets
    import aiohttp
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "websockets", "aiohttp"], check=True)
    import websockets
    import aiohttp

REPO_ROOT = Path(__file__).parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "starvector"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_VISEMES = ["sil", "PP", "aa", "O", "U", "I", "FF", "CH"]

GENERATION_CODE = '''
import os, sys, io, time, json, base64
import torch
import cairosvg
from PIL import Image
from pathlib import Path

sys.path.insert(0, "/workspace")
from svg_generator import build_face_svg, VISEMES

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = "starvector/starvector-1b-im2svg"
OUT = Path("/workspace/starvector_out")
OUT.mkdir(exist_ok=True)

TARGET_VISEMES = {target}

print(f"Device: {{DEVICE}}")
print(f"GPU: {{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}}")

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
print("Model loaded.")

results = []
for viseme_name in TARGET_VISEMES:
    if viseme_name not in VISEMES:
        print(f"  [skip] {{viseme_name}}")
        continue

    jaw, spread, part = VISEMES[viseme_name]["shape"]
    print(f"[{{viseme_name:4s}}]  jaw={{jaw:.2f}}  spread={{spread:+.2f}}  part={{part:+.2f}}")

    svg_str = build_face_svg(viseme_name, jaw, spread, part)
    png_bytes = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=224, output_height=224)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    input_path = OUT / f"{{viseme_name}}_input.png"
    img.save(input_path)

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
        print(f"  OK: {{len(raw_svg):,}} chars, {{elapsed:.1f}}s")
        results.append({{"viseme": viseme_name, "elapsed": elapsed, "svg_len": len(raw_svg)}})
    except Exception as e:
        print(f"  FAILED: {{e}}")

print("GENERATION_COMPLETE:" + json.dumps(results))
'''

INSTALL_CODE = '''
import subprocess, sys, importlib

def pip(*args):
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + list(args),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("pip STDERR:", r.stderr[-500:])
    return r.returncode

print("Python:", sys.executable)

# Step 1: cairosvg + all its deps (pre-installed cairosvg in /opt/venv is missing these)
rc = pip("cairocffi", "cssselect2", "defusedxml", "cairosvg")
print("cairocffi+cairosvg install:", "OK" if rc == 0 else f"FAILED ({rc})")

# Step 2: main ML packages (should be mostly pre-installed in /opt/venv)
pip("transformers==4.49.0", "tokenizers==0.21.1", "sentencepiece", "accelerate")

# Step 3: starvector without deps (avoid scipy/scikit-learn recompile)
rc = pip("--no-deps", "git+https://github.com/joanrod/star-vector.git")
print("starvector install:", "OK" if rc == 0 else f"FAILED ({rc})")

# Step 4: starvector non-scipy deps
pip("omegaconf", "fairscale", "svgpathtools", "webcolors", "beautifulsoup4")

importlib.invalidate_caches()

# Verify
try:
    import cairocffi
    print("cairocffi OK:", cairocffi.version)
except Exception as e:
    print("cairocffi FAILED:", e)

try:
    import cairosvg
    print("cairosvg OK:", cairosvg.__version__)
except Exception as e:
    print("cairosvg FAILED:", e)

try:
    from starvector.model.starvector_arch import StarVectorForCausalLM
    print("starvector OK")
except Exception as e:
    print("starvector FAILED:", e)

print("INSTALL_COMPLETE")
'''


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


async def upload_file(session: aiohttp.ClientSession, base_url: str, remote_path: str, content: str):
    """Upload a text file via Jupyter contents API."""
    url = f"{base_url}/api/contents/{remote_path}"
    payload = {
        "type": "file",
        "format": "text",
        "content": content,
    }
    async with session.put(url, json=payload) as resp:
        if resp.status not in (200, 201):
            body = await resp.text()
            raise RuntimeError(f"Upload failed ({resp.status}): {body[:200]}")


async def download_file(session: aiohttp.ClientSession, base_url: str, remote_path: str) -> bytes | None:
    """Download a binary file via Jupyter contents API (base64 encoded)."""
    url = f"{base_url}/api/contents/{remote_path}?format=base64"
    async with session.get(url) as resp:
        if resp.status == 404:
            return None
        if resp.status != 200:
            return None
        data = await resp.json()
        return base64.b64decode(data["content"])


async def list_dir(session: aiohttp.ClientSession, base_url: str, path: str) -> list[str]:
    """List files in a remote directory."""
    url = f"{base_url}/api/contents/{path}"
    async with session.get(url) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
        if data.get("type") != "directory":
            return []
        return [item["name"] for item in data.get("content", [])]


async def create_kernel(session: aiohttp.ClientSession, base_url: str) -> str:
    """Start a new Python kernel, return kernel ID."""
    async with session.post(f"{base_url}/api/kernels", json={"name": "python3"}) as resp:
        data = await resp.json()
        return data["id"]


async def delete_kernel(session: aiohttp.ClientSession, base_url: str, kernel_id: str):
    async with session.delete(f"{base_url}/api/kernels/{kernel_id}"):
        pass


async def execute_code(ws_base: str, kernel_id: str, code: str, timeout: int = 600) -> list[str]:
    """
    Execute code on a Jupyter kernel via WebSocket.
    Returns list of output strings.
    """
    ws_url = f"{ws_base}/api/kernels/{kernel_id}/channels"
    msg_id = str(uuid.uuid4()).replace("-", "")

    execute_msg = {
        "header": {
            "msg_id": msg_id,
            "msg_type": "execute_request",
            "version": "5.3",
            "username": "user",
            "session": str(uuid.uuid4()).replace("-", ""),
            "date": "",
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "code": code,
            "silent": False,
            "store_history": False,
            "user_expressions": {},
            "allow_stdin": False,
        },
        "buffers": [],
        "channel": "shell",
    }

    outputs = []
    deadline = time.time() + timeout

    async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as ws:
        await ws.send(json.dumps(execute_msg))

        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                break

            msg = json.loads(raw)
            msg_type = msg.get("header", {}).get("msg_type", "")
            parent_id = msg.get("parent_header", {}).get("msg_id", "")

            if parent_id != msg_id:
                continue

            if msg_type == "stream":
                text = msg["content"].get("text", "")
                print(text, end="", flush=True)
                outputs.append(text)

            elif msg_type == "display_data" or msg_type == "execute_result":
                text = msg["content"].get("data", {}).get("text/plain", "")
                if text:
                    print(text, flush=True)
                    outputs.append(text)

            elif msg_type == "error":
                tb = "\n".join(msg["content"].get("traceback", []))
                print(f"KERNEL ERROR:\n{tb}", flush=True)
                outputs.append(f"ERROR: {msg['content'].get('ename')}: {msg['content'].get('evalue')}")

            elif msg_type == "status":
                state = msg["content"].get("execution_state", "")
                if state == "idle":
                    break  # execution complete

    return outputs


async def main():
    load_dotenv()

    pod_id = os.environ.get("RUNPOD_POD_ID", "").strip() or "REDACTED_POD_ID"
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        hf_token_file = Path.home() / ".cache" / "huggingface" / "token"
        if hf_token_file.exists():
            hf_token = hf_token_file.read_text().strip()
    if not hf_token:
        sys.exit("HF_TOKEN not set")

    base_url = f"https://{pod_id}-8888.proxy.runpod.net"
    ws_base = f"wss://{pod_id}-8888.proxy.runpod.net"

    print(f"Jupyter: {base_url}")

    # Headers — RunPod proxy auth uses the RunPod API key
    api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async with aiohttp.ClientSession(headers=headers) as session:

        # 1. Verify Jupyter is up + grab XSRF token from cookies
        async with session.get(f"{base_url}/api") as resp:
            info = await resp.json()
            print(f"Jupyter {info['version']} — OK")

        # Fetch the login page (or tree) to seed _xsrf cookie
        async with session.get(f"{base_url}/tree") as resp:
            pass  # sets _xsrf cookie

        xsrf = session.cookie_jar.filter_cookies(base_url).get("_xsrf")
        if xsrf:
            xsrf_value = xsrf.value
            print(f"XSRF token obtained.")
            session.headers.update({"X-XSRFToken": xsrf_value})
        else:
            print("No XSRF token (may work without it).")

        # 2. Upload svg_generator.py
        print("\nUploading svg_generator.py...")
        svg_gen_content = (REPO_ROOT / "svg_generator.py").read_text()
        await upload_file(session, base_url, "svg_generator.py", svg_gen_content)
        print("  Done.")

        # 3. Start kernel
        print("\nStarting Python kernel...")
        kernel_id = await create_kernel(session, base_url)
        print(f"  Kernel: {kernel_id}")

        try:
            # 4. Set HF_TOKEN env var in kernel
            await execute_code(
                ws_base, kernel_id,
                f'import os; os.environ["HF_TOKEN"] = "{hf_token}"',
                timeout=30
            )

            # 5. Install dependencies
            print("\nInstalling StarVector deps (this takes ~3-5 min)...")
            await execute_code(ws_base, kernel_id, INSTALL_CODE, timeout=600)

            # 6. Run generation
            print("\nRunning StarVector im2svg on RTX PRO 6000...")
            code = GENERATION_CODE.format(target=repr(TARGET_VISEMES))
            outputs = await execute_code(ws_base, kernel_id, code, timeout=3600)

            # Parse summary from output
            combined = "".join(outputs)
            if "GENERATION_COMPLETE:" in combined:
                idx = combined.index("GENERATION_COMPLETE:")
                results_json = combined[idx + len("GENERATION_COMPLETE:"):].split("\n")[0]
                results = json.loads(results_json)
                print(f"\n{len(results)}/{len(TARGET_VISEMES)} visemes generated.")
            else:
                print("\nGeneration finished (no summary found).")

        finally:
            await delete_kernel(session, base_url, kernel_id)
            print("Kernel cleaned up.")

        # 7. Download outputs
        print("\nDownloading outputs...")
        files = await list_dir(session, base_url, "starvector_out")
        print(f"  Remote files: {files}")
        for fname in files:
            remote_path = f"starvector_out/{fname}"
            ext = Path(fname).suffix
            if ext in (".png", ".svg"):
                data = await download_file(session, base_url, remote_path)
                if data:
                    dest = OUT_DIR / fname
                    dest.write_bytes(data)
                    print(f"  Downloaded: {fname} ({len(data):,} bytes)")

    # 8. Write gallery
    write_gallery()
    print(f"\nDone. Outputs: {OUT_DIR}")


def write_gallery():
    png_files = sorted(OUT_DIR.glob("*_input.png"))
    if not png_files:
        return
    cards = []
    for png in png_files:
        viseme = png.stem.replace("_input", "")
        svg = OUT_DIR / f"{viseme}_output.svg"
        input_rel = png.relative_to(REPO_ROOT)
        if svg.exists():
            output_rel = svg.relative_to(REPO_ROOT)
            output_tag = f'<object type="image/svg+xml" data="../{output_rel}" width="256" height="256"><img src="../{input_rel}"/></object>'
        else:
            output_tag = '<p style="color:#f66">no output</p>'
        cards.append(f"""
      <div class="card">
        <div class="label">{viseme} — input</div>
        <img src="../{input_rel}" width="256" height="256"/>
        <div class="label">StarVector output</div>
        {output_tag}
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>StarVector Gallery</title>
<style>
  body{{background:#1a1a1a;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
  h1{{color:#fff;margin-bottom:16px}}
  .grid{{display:flex;flex-wrap:wrap;gap:20px}}
  .card{{background:#2a2a2a;border-radius:12px;padding:12px;text-align:center;width:270px}}
  .label{{font-size:12px;color:#aaa;margin:6px 0 4px}}
</style></head>
<body>
  <h1>StarVector im2svg — Cartoon Viseme Faces (RTX PRO 6000)</h1>
  <p style="color:#888">Input: parametric SVG rasterized to 224×224 PNG. Output: StarVector 1B trace.</p>
  <div class="grid">{"".join(cards)}</div>
</body></html>"""

    out = OUT_DIR / "gallery.html"
    out.write_text(html)
    import subprocess
    subprocess.run(["open", str(out)], check=False)
    print(f"Gallery: {out}")


if __name__ == "__main__":
    asyncio.run(main())
