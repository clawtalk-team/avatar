import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# ComfyUI job polling config
POLL_INTERVAL = 5  # seconds between status checks
DEFAULT_TIMEOUT = 600  # 10 minutes


class ComfyUIError(Exception):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str, api_key: str):
        """api_key is the RunPod API key used as a Bearer token for proxy authentication."""
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | bytes:
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(raw)
                return raw
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            raise ComfyUIError(f"ComfyUI {method} {path} returned {e.code}: {body_text}") from e
        except Exception as e:
            raise ComfyUIError(f"ComfyUI request failed: {e}") from e

    def _request_binary(self, path: str) -> bytes:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}", "User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise ComfyUIError(f"ComfyUI GET {path} returned {e.code}") from e
        except Exception as e:
            raise ComfyUIError(f"ComfyUI binary request failed: {e}") from e

    def submit_prompt(self, workflow: dict) -> str:
        """Submit a workflow prompt to ComfyUI. Returns prompt_id."""
        result = self._request("POST", "/prompt", {"prompt": workflow})
        if not isinstance(result, dict) or "prompt_id" not in result:
            raise ComfyUIError(f"Unexpected /prompt response: {result}")
        prompt_id = result["prompt_id"]
        logger.info(f"Submitted ComfyUI prompt: {prompt_id}")
        return prompt_id

    def poll_until_done(self, prompt_id: str, timeout: int = DEFAULT_TIMEOUT) -> list[dict]:
        """Poll /history until the prompt completes. Returns list of output file dicts.

        Each dict has keys: filename, subfolder, type.
        Raises ComfyUIError if the job fails or times out.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            history = self._request("GET", f"/history/{prompt_id}")
            if not isinstance(history, dict):
                raise ComfyUIError(f"Unexpected /history response type: {type(history)}")

            if prompt_id not in history:
                # Not finished yet
                time.sleep(POLL_INTERVAL)
                continue

            entry = history[prompt_id]
            status = entry.get("status", {})

            if status.get("status_str") == "error" or status.get("completed") is False:
                messages = status.get("messages", [])
                raise ComfyUIError(f"ComfyUI job failed: {messages}")

            # Collect output files (images / videos) from all nodes
            outputs = entry.get("outputs", {})
            files = []
            for node_id, node_out in outputs.items():
                for gifs in node_out.get("gifs", []):
                    files.append(gifs)
                for imgs in node_out.get("images", []):
                    files.append(imgs)
            if files:
                logger.info(f"ComfyUI prompt {prompt_id} done, {len(files)} output file(s)")
                return files

            # Completed but no outputs — treat as error
            raise ComfyUIError(f"ComfyUI prompt {prompt_id} completed with no output files")

        raise ComfyUIError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")

    def download_output(self, filename: str, subfolder: str = "", file_type: str = "output") -> bytes:
        """Download a generated output file from ComfyUI."""
        params = f"filename={urllib.parse.quote(filename)}&type={file_type}"
        if subfolder:
            params += f"&subfolder={urllib.parse.quote(subfolder)}"
        return self._request_binary(f"/view?{params}")
