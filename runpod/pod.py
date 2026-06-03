#!/usr/bin/env python3
"""
RunPod pod lifecycle management for the ComfyUI / Wan 2.2 avatar pod.

Usage:
  python runpod/pod.py status
  python runpod/pod.py start
  python runpod/pod.py stop
  python runpod/pod.py url   # print proxy URL if running

Environment variables (set in .env at project root, or export directly):
  RUNPOD_API_KEY   – RunPod API key
  RUNPOD_POD_ID    – Pod ID to manage
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"
COMFYUI_PORT = 8188

START_TIMEOUT = 300   # seconds to wait for pod to reach RUNNING
POLL_INTERVAL = 10    # seconds between status checks


def load_dotenv() -> None:
    """Load .env from the project root (parent of this script's directory) into os.environ."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v


def get_required(var: str) -> str:
    val = os.environ.get(var, "").strip()
    if not val:
        sys.exit(f"Error: {var} is not set. Add it to .env or export it.")
    return val


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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"RunPod API error {e.code}: {e.read().decode()}")
    if "errors" in body:
        sys.exit(f"RunPod GraphQL errors: {body['errors']}")
    return body["data"]


def pod_status(api_key: str, pod_id: str) -> dict:
    data = graphql(api_key, """
        query($podId: String!) {
            pod(input: { podId: $podId }) {
                id name desiredStatus
                runtime { uptimeInSeconds }
            }
        }
    """, {"podId": pod_id})
    return data["pod"]


def pod_proxy_url(pod_id: str) -> str:
    return f"https://{pod_id}-{COMFYUI_PORT}.proxy.runpod.net"


def cmd_status(api_key: str, pod_id: str):
    pod = pod_status(api_key, pod_id)
    status = pod["desiredStatus"]
    url = pod_proxy_url(pod_id) if status == "RUNNING" else "—"
    uptime = pod.get("runtime") or {}
    uptime_s = uptime.get("uptimeInSeconds", 0)
    uptime_str = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m" if uptime_s else "—"
    print(f"Pod:    {pod['name']} ({pod_id})")
    print(f"Status: {status}")
    print(f"Uptime: {uptime_str}")
    print(f"URL:    {url}")


def cmd_url(api_key: str, pod_id: str):
    pod = pod_status(api_key, pod_id)
    if pod["desiredStatus"] != "RUNNING":
        sys.exit(f"Pod is not running (status: {pod['desiredStatus']}). Run: python runpod/pod.py start")
    print(pod_proxy_url(pod_id))


def cmd_start(api_key: str, pod_id: str):
    pod = pod_status(api_key, pod_id)
    if pod["desiredStatus"] == "RUNNING":
        print(f"Pod already running: {pod_proxy_url(pod_id)}")
        return

    print(f"Starting pod {pod_id}...")
    graphql(api_key, """
        mutation($podId: String!, $gpuCount: Int!) {
            podResume(input: { podId: $podId, gpuCount: $gpuCount }) {
                id desiredStatus
            }
        }
    """, {"podId": pod_id, "gpuCount": 1})

    deadline = time.time() + START_TIMEOUT
    dots = 0
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        dots += 1
        print(f"\rWaiting for pod to start... {dots * POLL_INTERVAL}s", end="", flush=True)
        pod = pod_status(api_key, pod_id)
        if pod["desiredStatus"] == "RUNNING" and pod.get("runtime"):
            print()
            url = pod_proxy_url(pod_id)
            print(f"Pod running: {url}")
            print(f"\nNote: ComfyUI may take another 30-60s to fully load models.")
            print(f"Export for generation scripts:")
            print(f"  export COMFYUI_URL={url}")
            return

    print()
    sys.exit(f"Timed out waiting for pod to start after {START_TIMEOUT}s")


def cmd_stop(api_key: str, pod_id: str):
    pod = pod_status(api_key, pod_id)
    if pod["desiredStatus"] == "EXITED":
        print("Pod is already stopped.")
        return

    print(f"Stopping pod {pod_id}...")
    graphql(api_key, """
        mutation($podId: String!) {
            podStop(input: { podId: $podId }) {
                id desiredStatus
            }
        }
    """, {"podId": pod_id})
    print("Pod stop requested. Model weights are preserved on the network volume.")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Manage the RunPod ComfyUI avatar pod")
    parser.add_argument("command", choices=["status", "start", "stop", "url"])
    args = parser.parse_args()

    api_key = get_required("RUNPOD_API_KEY")
    pod_id = get_required("RUNPOD_POD_ID")

    if args.command == "status":
        cmd_status(api_key, pod_id)
    elif args.command == "start":
        cmd_start(api_key, pod_id)
    elif args.command == "stop":
        cmd_stop(api_key, pod_id)
    elif args.command == "url":
        cmd_url(api_key, pod_id)


if __name__ == "__main__":
    main()
