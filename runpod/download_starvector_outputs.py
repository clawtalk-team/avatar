#!/usr/bin/env python3
"""Download StarVector SVG outputs from the RunPod pod via Jupyter API."""
import asyncio, base64, json, os, sys, uuid
from pathlib import Path

try:
    import aiohttp
    import websockets
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "aiohttp", "websockets"], check=True)
    import aiohttp
    import websockets

REPO_ROOT = Path(__file__).parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "starvector"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
env_file = REPO_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

FETCH_CODE = '''
import base64, json
from pathlib import Path

out_dir = Path("/workspace/starvector_out")
results = {}
if out_dir.exists():
    for f in sorted(out_dir.iterdir()):
        if f.suffix in (".svg", ".png"):
            data = f.read_bytes()
            results[f.name] = base64.b64encode(data).decode()
else:
    print("DIR_NOT_FOUND:/workspace/starvector_out")

print("FILES:" + json.dumps(list(results.keys())))
for name, b64 in results.items():
    print(f"FILE:{name}:{b64}")
print("FETCH_COMPLETE")
'''


async def execute_code(ws_base, kernel_id, code, timeout=120):
    ws_url = f"{ws_base}/api/kernels/{kernel_id}/channels"
    msg_id = str(uuid.uuid4()).replace("-", "")
    execute_msg = {
        "header": {"msg_id": msg_id, "msg_type": "execute_request", "version": "5.3",
                   "username": "user", "session": str(uuid.uuid4()).replace("-", ""), "date": ""},
        "parent_header": {}, "metadata": {},
        "content": {"code": code, "silent": False, "store_history": False,
                    "user_expressions": {}, "allow_stdin": False},
        "channel": "shell",
    }
    outputs = []
    async with websockets.connect(ws_url, additional_headers={}, open_timeout=30) as ws:
        await ws.send(json.dumps(execute_msg))
        import asyncio as _a
        async def recv():
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                msg_type = msg.get("msg_type", "")
                parent_id = msg.get("parent_header", {}).get("msg_id", "")
                if parent_id != msg_id:
                    continue
                if msg_type == "stream":
                    text = msg["content"].get("text", "")
                    print(text, end="", flush=True)
                    outputs.append(text)
                elif msg_type in ("execute_result", "display_data"):
                    text = msg["content"].get("data", {}).get("text/plain", "")
                    if text:
                        print(text, flush=True)
                        outputs.append(text)
                elif msg_type == "error":
                    tb = "\n".join(msg["content"].get("traceback", []))
                    print(f"KERNEL ERROR:\n{tb}", flush=True)
                    outputs.append(f"ERROR: {msg['content'].get('ename')}: {msg['content'].get('evalue')}")
                elif msg_type == "status":
                    if msg["content"].get("execution_state") == "idle":
                        break
        await _a.wait_for(recv(), timeout=timeout)
    return outputs


async def main():
    pod_id = os.environ.get("RUNPOD_POD_ID", "").strip()
    if not pod_id:
        print("RUNPOD_POD_ID not set"); return
    api_key = os.environ.get("RUNPOD_API_KEY", "").strip()

    base_url = f"https://{pod_id}-8888.proxy.runpod.net"
    ws_base = f"wss://{pod_id}-8888.proxy.runpod.net"

    print(f"Connecting to {base_url} ...")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async with aiohttp.ClientSession(headers=headers) as session:
        # Seed XSRF
        async with session.get(f"{base_url}/tree") as resp:
            pass
        xsrf = session.cookie_jar.filter_cookies(base_url).get("_xsrf")
        if xsrf:
            session.headers.update({"X-XSRFToken": xsrf.value})

        # Start kernel
        async with session.post(f"{base_url}/api/kernels", json={"name": "python3"}) as resp:
            data = await resp.json()
            kernel_id = data["id"]
        print(f"Kernel: {kernel_id}")

        try:
            outputs = await execute_code(ws_base, kernel_id, FETCH_CODE, timeout=60)
        finally:
            async with session.delete(f"{base_url}/api/kernels/{kernel_id}"):
                pass
            print("Kernel cleaned up.")

    # Parse outputs
    combined = "".join(outputs)
    lines = combined.splitlines()
    files_line = next((l for l in lines if l.startswith("FILES:")), None)
    if files_line:
        names = json.loads(files_line[len("FILES:"):])
        print(f"\nFound {len(names)} files: {names}")
    else:
        print("No FILES: line found in output.")
        return

    # Extract FILE: lines and save
    saved = []
    for line in lines:
        if line.startswith("FILE:"):
            parts = line[5:].split(":", 1)
            if len(parts) == 2:
                fname, b64 = parts
                data = base64.b64decode(b64)
                dest = OUT_DIR / fname
                dest.write_bytes(data)
                print(f"  Saved: {fname} ({len(data):,} bytes)")
                saved.append(fname)

    if "FETCH_COMPLETE" in combined:
        print(f"\nDone. {len(saved)} files saved to {OUT_DIR}")
    else:
        print("\nFETCH_COMPLETE not seen — may have timed out.")


if __name__ == "__main__":
    asyncio.run(main())
