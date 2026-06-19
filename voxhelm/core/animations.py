"""Animation mode definitions — idle, listening, thinking.

Each mode is a looped keyframe sequence that applies transforms to the
structured SVG groups (head, eyes, brows, mouth).  Every sequence starts
and ends at the neutral pose (identity transform) so that mode switches
are instantaneous and glitch-free.

Transforms are expressed as dicts with:
    tx, ty  — translate (px in SVG 512-space)
    r       — rotate (degrees, around group center)
    sx, sy  — scale (1.0 = identity)

A keyframe is: {"t": <0..1 fraction of loop>, "groups": {group_id: transform}}

The player interpolates linearly between keyframes and applies the
transforms at runtime via CSS/JS (web) or Canvas transforms (Flutter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnimationMode(str, Enum):
    """Avatar animation modes."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"


# Neutral transform — identity; every sequence starts and ends here.
NEUTRAL: dict[str, float] = {"tx": 0, "ty": 0, "r": 0, "sx": 1.0, "sy": 1.0}


def _n() -> dict[str, float]:
    """Return a fresh copy of the neutral transform."""
    return dict(NEUTRAL)


@dataclass
class AnimationKeyframe:
    """A single keyframe in an animation sequence."""
    t: float  # 0..1, position in the loop
    groups: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"t": self.t, "groups": self.groups}


@dataclass
class AnimationSequence:
    """A looped animation defined as a list of keyframes."""
    mode: AnimationMode
    duration_ms: int  # total loop duration in milliseconds
    keyframes: list[AnimationKeyframe] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "duration_ms": self.duration_ms,
            "keyframes": [kf.to_dict() for kf in self.keyframes],
        }


# ── Idle ────────────────────────────────────────────────────────────────────
# Gentle breathing motion with visible head sway and gaze drift.
# Slow and calm — 4 second loop.

IDLE_SEQUENCE = AnimationSequence(
    mode=AnimationMode.IDLE,
    duration_ms=4000,
    keyframes=[
        # 0.00 — neutral start
        AnimationKeyframe(t=0.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
        # 0.15 — inhale: head lifts, eyes drift right
        AnimationKeyframe(t=0.15, groups={
            "head":  {"tx": 2, "ty": -6, "r": 1.2, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 4, "ty": -2, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": -3, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.35 — peak of breath, rightward drift
        AnimationKeyframe(t=0.35, groups={
            "head":  {"tx": 5, "ty": -10, "r": 2.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 6, "ty": -3, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": -4, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.50 — exhale starts, settle back
        AnimationKeyframe(t=0.50, groups={
            "head":  {"tx": 2, "ty": -4, "r": 0.8, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 2, "ty": -1, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": -2, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.70 — exhale continues, left drift
        AnimationKeyframe(t=0.70, groups={
            "head":  {"tx": -4, "ty": 2, "r": -1.5, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": -5, "ty": 2, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": 1, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.85 — settling back to neutral
        AnimationKeyframe(t=0.85, groups={
            "head":  {"tx": -2, "ty": 1, "r": -0.5, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": -2, "ty": 0, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": _n(),
            "mouth": _n(),
        }),
        # 1.00 — back to neutral (loop point)
        AnimationKeyframe(t=1.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
    ],
)


# ── Listening ───────────────────────────────────────────────────────────────
# Attentive, focused — forward lean, visible nods, engaged head tilt.
# 3 second loop, more active than idle.

LISTENING_SEQUENCE = AnimationSequence(
    mode=AnimationMode.LISTENING,
    duration_ms=3000,
    keyframes=[
        # 0.00 — neutral start
        AnimationKeyframe(t=0.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
        # 0.10 — lean forward (listening intently)
        AnimationKeyframe(t=0.10, groups={
            "head":  {"tx": 0, "ty": -8, "r": -1.5, "sx": 1.005, "sy": 1.005},
            "eyes":  {"tx": 0, "ty": 0, "r": 0, "sx": 1.02, "sy": 1.04},
            "brows": {"tx": 0, "ty": -5, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.25 — nod down (acknowledgement)
        AnimationKeyframe(t=0.25, groups={
            "head":  {"tx": 0, "ty": 8, "r": -3.0, "sx": 1.005, "sy": 1.005},
            "eyes":  {"tx": 0, "ty": 3, "r": 0, "sx": 1.02, "sy": 1.04},
            "brows": {"tx": 0, "ty": -3, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.35 — nod back up
        AnimationKeyframe(t=0.35, groups={
            "head":  {"tx": 0, "ty": -6, "r": -1.0, "sx": 1.005, "sy": 1.005},
            "eyes":  {"tx": 2, "ty": -2, "r": 0, "sx": 1.02, "sy": 1.04},
            "brows": {"tx": 0, "ty": -4, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.55 — head tilt (engaged)
        AnimationKeyframe(t=0.55, groups={
            "head":  {"tx": 7, "ty": -4, "r": 4.0, "sx": 1.005, "sy": 1.005},
            "eyes":  {"tx": -3, "ty": 0, "r": 0, "sx": 1.02, "sy": 1.04},
            "brows": {"tx": 0, "ty": -3, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.70 — second smaller nod
        AnimationKeyframe(t=0.70, groups={
            "head":  {"tx": 4, "ty": 4, "r": 2.5, "sx": 1.003, "sy": 1.003},
            "eyes":  {"tx": -2, "ty": 2, "r": 0, "sx": 1.01, "sy": 1.02},
            "brows": {"tx": 0, "ty": -2, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.85 — settling
        AnimationKeyframe(t=0.85, groups={
            "head":  {"tx": 2, "ty": -2, "r": 1.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 0, "ty": 0, "r": 0, "sx": 1.005, "sy": 1.01},
            "brows": {"tx": 0, "ty": -1, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 1.00 — neutral (loop point)
        AnimationKeyframe(t=1.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
    ],
)


# ── Thinking ────────────────────────────────────────────────────────────────
# Contemplative — eyes clearly drift up/sideways, brow furrow, head tilts.
# 5 second loop, deliberate and slower.

THINKING_SEQUENCE = AnimationSequence(
    mode=AnimationMode.THINKING,
    duration_ms=5000,
    keyframes=[
        # 0.00 — neutral start
        AnimationKeyframe(t=0.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
        # 0.10 — eyes start drifting up-right (recall)
        AnimationKeyframe(t=0.10, groups={
            "head":  {"tx": 3, "ty": -3, "r": 2.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 12, "ty": -10, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": -2, "r": -1.5, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.25 — full look-away, brows knit
        AnimationKeyframe(t=0.25, groups={
            "head":  {"tx": 8, "ty": -6, "r": 5.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 18, "ty": -15, "r": 0, "sx": 1.0, "sy": 0.92},
            "brows": {"tx": 0, "ty": 5, "r": -3.0, "sx": 1.0, "sy": 0.9},
            "mouth": _n(),
        }),
        # 0.40 — hold thinking gaze, head tilts further
        AnimationKeyframe(t=0.40, groups={
            "head":  {"tx": 10, "ty": -4, "r": 6.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": 15, "ty": -14, "r": 0, "sx": 1.0, "sy": 0.92},
            "brows": {"tx": 0, "ty": 6, "r": -2.5, "sx": 1.0, "sy": 0.88},
            "mouth": {"tx": 2, "ty": 0, "r": 0, "sx": 0.95, "sy": 0.92},
        }),
        # 0.55 — eyes shift left (considering alternative)
        AnimationKeyframe(t=0.55, groups={
            "head":  {"tx": -5, "ty": -3, "r": -3.0, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": -12, "ty": -8, "r": 0, "sx": 1.0, "sy": 0.95},
            "brows": {"tx": 0, "ty": 4, "r": 1.5, "sx": 1.0, "sy": 0.92},
            "mouth": {"tx": -1, "ty": 0, "r": 0, "sx": 0.96, "sy": 0.94},
        }),
        # 0.70 — brow raise (insight moment)
        AnimationKeyframe(t=0.70, groups={
            "head":  {"tx": -3, "ty": -6, "r": -1.5, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": -4, "ty": -4, "r": 0, "sx": 1.02, "sy": 1.06},
            "brows": {"tx": 0, "ty": -8, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 0.85 — settling back
        AnimationKeyframe(t=0.85, groups={
            "head":  {"tx": -1, "ty": -2, "r": -0.5, "sx": 1.0, "sy": 1.0},
            "eyes":  {"tx": -2, "ty": -2, "r": 0, "sx": 1.0, "sy": 1.0},
            "brows": {"tx": 0, "ty": -3, "r": 0, "sx": 1.0, "sy": 1.0},
            "mouth": _n(),
        }),
        # 1.00 — neutral (loop point)
        AnimationKeyframe(t=1.0, groups={
            "head":  _n(),
            "eyes":  _n(),
            "brows": _n(),
            "mouth": _n(),
        }),
    ],
)


# ── Registry ────────────────────────────────────────────────────────────────

ANIMATIONS: dict[AnimationMode, AnimationSequence] = {
    AnimationMode.IDLE: IDLE_SEQUENCE,
    AnimationMode.LISTENING: LISTENING_SEQUENCE,
    AnimationMode.THINKING: THINKING_SEQUENCE,
}


def get_animation(mode: AnimationMode | str) -> AnimationSequence:
    """Get an animation sequence by mode name."""
    if isinstance(mode, str):
        mode = AnimationMode(mode)
    return ANIMATIONS[mode]


def get_all_animations() -> dict[str, dict]:
    """Return all animations as a JSON-serialisable dict."""
    return {m.value: s.to_dict() for m, s in ANIMATIONS.items()}


def interpolate_transform(
    a: dict[str, float],
    b: dict[str, float],
    t: float,
) -> dict[str, float]:
    """Linearly interpolate between two transforms at fraction t (0..1)."""
    return {
        "tx": a["tx"] + (b["tx"] - a["tx"]) * t,
        "ty": a["ty"] + (b["ty"] - a["ty"]) * t,
        "r":  a["r"]  + (b["r"]  - a["r"])  * t,
        "sx": a["sx"] + (b["sx"] - a["sx"]) * t,
        "sy": a["sy"] + (b["sy"] - a["sy"]) * t,
    }


def sample_animation(
    seq: AnimationSequence,
    t_norm: float,
) -> dict[str, dict[str, float]]:
    """Sample the animation at a normalised time (0..1), returning group transforms.

    Finds the surrounding keyframes and interpolates between them.
    """
    t_norm = t_norm % 1.0  # wrap for looping
    kfs = seq.keyframes

    # Find bracketing keyframes
    prev = kfs[0]
    nxt = kfs[-1]
    for i in range(len(kfs) - 1):
        if kfs[i].t <= t_norm <= kfs[i + 1].t:
            prev = kfs[i]
            nxt = kfs[i + 1]
            break

    # Local interpolation factor
    span = nxt.t - prev.t
    local_t = (t_norm - prev.t) / span if span > 0 else 0.0

    # Smooth ease-in-out
    local_t = local_t * local_t * (3.0 - 2.0 * local_t)

    result: dict[str, dict[str, float]] = {}
    all_groups = set(prev.groups.keys()) | set(nxt.groups.keys())
    for group in all_groups:
        a = prev.groups.get(group, NEUTRAL)
        b = nxt.groups.get(group, NEUTRAL)
        result[group] = interpolate_transform(a, b, local_t)

    return result


# ── Video-based animation generation ─────────────────────────────────────

# Prompts per mode — derived from behavioural research.
ANIM_PROMPTS: dict[AnimationMode, str] = {
    AnimationMode.IDLE: (
        "Animate this cartoon character sitting idle and slightly bored. "
        "The head slowly droops and lolls to one side, eyelids become heavy "
        "and half-closed. The gaze drifts lazily around — looking off to the "
        "right, then slowly wandering down and to the left. A slow blink. "
        "The head straightens slightly then droops to the other side. Languid, "
        "low-energy movement. The character sighs — shoulders drop slightly. "
        "Visible head movement tilting side to side. Dark background. No talking."
    ),
    AnimationMode.LISTENING: (
        "Animate this cartoon character actively listening to someone speaking. "
        "The head tilts to one side attentively, eyes wide and focused. The "
        "character nods — a clear downward head dip then back up. The head then "
        "cocks to the other side with interest. Another small nod of "
        "acknowledgement. Eyebrows raise briefly at something interesting. The "
        "head turns slightly toward the speaker. Alert, engaged, responsive "
        "movements. Visible head tilting and nodding throughout. Dark background. "
        "No talking."
    ),
    AnimationMode.THINKING: (
        "Animate this cartoon character thinking hard about a problem. The head "
        "tilts to the right while eyes look upward and to the right — accessing "
        "a memory. The brow furrows in concentration. The head slowly turns to "
        "look up and to the left, considering alternatives. Eyes briefly close "
        "in deep thought, then open wide with a flash of insight — eyebrows "
        "shoot up. The head returns toward centre. Clear visible head movement "
        "— turning, tilting, nodding slightly. Dark background. No talking."
    ),
}

# Modes where the last_frame constraint is used for looping.
# Thinking gets more freedom without it.
_LOOP_MODES = {AnimationMode.IDLE, AnimationMode.LISTENING}

DEFAULT_VIDEO_MODEL = "google/veo-3.1-lite"
DEFAULT_VIDEO_DURATION = 4
DEFAULT_VIDEO_RESOLUTION = "720p"


def render_svg_to_png(svg_path: str, out_path: str, size: int = 720) -> str:
    """Render an SVG file to PNG using rsvg-convert."""
    import subprocess
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), svg_path, "-o", out_path],
        check=True,
    )
    return out_path


def submit_anim_video(
    png_path: str,
    mode: AnimationMode,
    api_key: str,
    model: str = DEFAULT_VIDEO_MODEL,
    duration: int = DEFAULT_VIDEO_DURATION,
    resolution: str = DEFAULT_VIDEO_RESOLUTION,
) -> dict:
    """Submit an animation video generation job to OpenRouter.

    Returns the job response dict with id and polling_url.
    """
    import base64
    import json
    import urllib.request

    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    data_url = f"data:image/png;base64,{b64}"

    prompt = ANIM_PROMPTS[mode]
    use_last_frame = mode in _LOOP_MODES

    frame_images = [
        {"type": "image_url", "image_url": {"url": data_url}, "frame_type": "first_frame"},
    ]
    if use_last_frame:
        frame_images.append(
            {"type": "image_url", "image_url": {"url": data_url}, "frame_type": "last_frame"},
        )

    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "frame_images": frame_images,
    }

    # Allow person generation for Google models (avoids content filtering)
    if "google/" in model or "veo" in model:
        body["provider"] = {
            "options": {
                "google-vertex": {
                    "parameters": {
                        "personGeneration": "allow",
                    }
                }
            }
        }

    payload = json.dumps(body).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/videos",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def poll_anim_video(
    job_id: str,
    api_key: str,
    timeout_s: int = 300,
    interval_s: int = 15,
) -> dict:
    """Poll until the video job completes or fails.

    Returns the final job response dict.
    """
    import json
    import time
    import urllib.request

    url = f"https://openrouter.ai/api/v1/videos/{job_id}"
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        time.sleep(interval_s)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        status = data.get("status")
        if status == "completed":
            return data
        if status in ("failed", "cancelled", "expired"):
            raise RuntimeError(
                f"Video generation {status}: {data.get('error', 'unknown')}"
            )

    raise TimeoutError(f"Video job {job_id} did not complete in {timeout_s}s")


def download_anim_video(job_data: dict, out_path: str, api_key: str) -> str:
    """Download the completed video MP4."""
    import urllib.request

    urls = job_data.get("unsigned_urls") or []
    if not urls:
        raise RuntimeError(
            "Video generation completed with no output "
            "(content may have been filtered)"
        )

    req = urllib.request.Request(urls[0], headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(out_path, "wb") as f:
            f.write(resp.read())
    return out_path


def extract_frames(mp4_path: str, out_dir: str, prefix: str, fps: int = 8) -> list[str]:
    """Extract frames from MP4 at the given FPS using ffmpeg.

    Returns list of output PNG file paths.
    """
    import glob
    import subprocess
    from pathlib import Path

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pattern = f"{out_dir}/{prefix}_%03d.png"

    subprocess.run(
        ["ffmpeg", "-y", "-i", mp4_path, "-vf", f"fps={fps}", pattern],
        check=True,
        capture_output=True,
    )

    return sorted(glob.glob(f"{out_dir}/{prefix}_*.png"))


def generate_anim_video(
    name: str,
    mode: AnimationMode | str,
    api_key: str,
    out_root: str = "outputs/heads",
    model: str = DEFAULT_VIDEO_MODEL,
    fps: int = 8,
    on_progress: Any = None,
) -> list[str]:
    """Full pipeline: render SVG → generate video → extract frames.

    Returns list of extracted frame PNG paths.
    """
    import logging
    from pathlib import Path

    log = logging.getLogger("voxhelm")

    if isinstance(mode, str):
        mode = AnimationMode(mode)

    head_dir = Path(out_root) / name
    sil_svg = head_dir / "sil.svg"
    sil_png = head_dir / "sil.png"

    if not sil_svg.exists():
        # Try PNG base for photo mode
        if not sil_png.exists():
            raise FileNotFoundError(f"No sil.svg or sil.png in {head_dir}")

    # 1. Render SVG to PNG (or use existing PNG)
    if on_progress:
        on_progress(f"{mode.value}_render", 0, 4, "generating")

    neutral_png = str(head_dir / "_neutral.png")
    if sil_svg.exists():
        render_svg_to_png(str(sil_svg), neutral_png)
    else:
        # Photo mode — sil.png already exists
        neutral_png = str(sil_png)

    log.info("Neutral PNG ready: %s", neutral_png)
    if on_progress:
        on_progress(f"{mode.value}_render", 1, 4, "ok")

    # 2. Submit video generation
    if on_progress:
        on_progress(f"{mode.value}_submit", 1, 4, "generating")

    job = submit_anim_video(neutral_png, mode, api_key, model=model)
    job_id = job["id"]
    log.info("Video job submitted: %s", job_id)
    if on_progress:
        on_progress(f"{mode.value}_submit", 2, 4, "ok")

    # 3. Poll until done (with progress updates)
    if on_progress:
        on_progress(f"{mode.value}_waiting", 2, 4, "generating")

    import json
    import time as _time
    import urllib.request
    url = f"https://openrouter.ai/api/v1/videos/{job_id}"
    deadline = _time.time() + 300
    poll_count = 0
    while _time.time() < deadline:
        _time.sleep(15)
        poll_count += 1
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        status = data.get("status")
        if on_progress:
            on_progress(f"{mode.value}_poll_{poll_count}", 2, 4, f"poll: {status}")
        if status == "completed":
            result = data
            break
        if status in ("failed", "cancelled", "expired"):
            raise RuntimeError(f"Video {status}: {data.get('error', 'unknown')}")
    else:
        raise TimeoutError(f"Video job {job_id} did not complete in 300s")

    log.info("Video completed: cost=%s", result.get("usage", {}).get("cost"))
    if on_progress:
        on_progress(f"{mode.value}_video_done", 3, 4, "ok")

    # 4. Download + extract frames
    if on_progress:
        on_progress(f"{mode.value}_frames", 3, 4, "generating")

    anim_dir = head_dir / "anim"
    anim_dir.mkdir(exist_ok=True)

    mp4_path = str(anim_dir / f"{mode.value}.mp4")
    download_anim_video(result, mp4_path, api_key)

    frames = extract_frames(mp4_path, str(anim_dir), mode.value, fps=fps)
    log.info("Extracted %d frames → %s", len(frames), anim_dir)
    if on_progress:
        on_progress(f"{mode.value}_frames", 4, 4, "ok")

    return frames
