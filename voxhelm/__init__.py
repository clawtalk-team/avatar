"""Voxhelm — SVG avatar generation and audio-driven lip-sync toolkit."""

__version__ = "0.2.0"

import logging
import os
from pathlib import Path

log = logging.getLogger("voxhelm")

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env(env_file: Path | None = None) -> None:
    """Load .env file into os.environ (does not overwrite existing vars)."""
    path = env_file or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip()
        if k and k not in os.environ:
            os.environ[k] = v
