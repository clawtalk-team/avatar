"""Voxhelm CLI — SVG avatar generation and lip-sync toolkit."""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import typer

from voxhelm import REPO_ROOT, load_env

app = typer.Typer(
    name="voxhelm",
    help="SVG avatar generation and audio-driven lip-sync toolkit.",
    no_args_is_help=True,
)

HEADS_DIR = REPO_ROOT / "outputs" / "heads"


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="  %(message)s",
        handlers=[logging.StreamHandler()],
    )


@app.command()
def generate(
    preset: str = typer.Option(None, help="Use a bundled character preset"),
    style: str = typer.Option(None, help="Custom style description"),
    name: str = typer.Option(None, help="Output directory name"),
    list_presets: bool = typer.Option(False, "--list-presets", help="List available presets"),
    model: str = typer.Option("claude-opus-4-6", help="Claude model"),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip existing SVGs"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate a set of 15 viseme SVGs for a character."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.core.presets import PRESETS
    from voxhelm.core.generator import generate as gen

    if list_presets:
        typer.echo("\nAvailable presets:\n")
        for k, v in PRESETS.items():
            typer.echo(f"  --preset {k}")
            typer.echo(f"    {v}\n")
        return

    if preset:
        if preset not in PRESETS:
            typer.echo(f"Unknown preset: {preset}", err=True)
            raise typer.Exit(1)
        resolved_style = PRESETS[preset]
        resolved_name = name or preset
    elif style:
        resolved_style = style
        resolved_name = name or re.sub(r"[^a-z0-9]+", "_", style[:40].lower()).strip("_")
    else:
        typer.echo("Provide --style or --preset (or --list-presets to see options)", err=True)
        raise typer.Exit(1)

    out_root = REPO_ROOT / out

    def progress(viseme: str, idx: int, total: int, status: str) -> None:
        typer.echo(f"  [{idx+1:2d}/{total}] {viseme:4s}  {status}")

    gallery = gen(
        style=resolved_style,
        name=resolved_name,
        model=model,
        out_root=out_root,
        skip_existing=skip_existing,
        on_progress=progress,
    )

    typer.echo(f"\nGallery: {gallery}")
    subprocess.run(["open", str(gallery)], check=False)


@app.command()
def speak(
    head: str = typer.Option(..., help="Head name (directory in outputs/heads/)"),
    text: str = typer.Option(..., help="Text to speak"),
    out: str = typer.Option(None, help="Output HTML path (default: outputs/speak_demo.html)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate TTS audio with viseme timeline and write a playback demo."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
    from voxhelm.core.timeline import words_to_timeline
    from voxhelm.core.generator import load_svgs

    head_dir = HEADS_DIR / head
    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    svgs = load_svgs(head_dir)
    if not svgs:
        typer.echo(f"No SVGs found in {head_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loaded {len(svgs)} SVGs for '{head}'")

    # Generate audio and timeline
    audio_bytes = deepgram_tts(text)
    words = deepgram_stt_words(audio_bytes)
    timeline = words_to_timeline(words)

    typer.echo(f"Timeline: {len(timeline)} events")

    # Write self-contained HTML
    audio_b64 = base64.b64encode(audio_bytes).decode()
    out_path = Path(out) if out else REPO_ROOT / "outputs" / "speak_demo.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    _write_speak_html(out_path, svgs, text, audio_b64, timeline)
    typer.echo(f"\nDemo: {out_path}")
    subprocess.run(["open", str(out_path)], check=False)


@app.command()
def validate(
    head: str = typer.Option(..., help="Head name to validate"),
    port: int = typer.Option(0, help="Port for web viewer (0=auto)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Launch a web viewer to validate a generated head's SVGs."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.core.generator import load_svgs

    head_dir = HEADS_DIR / head
    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    svgs = load_svgs(head_dir)
    typer.echo(f"Loaded {len(svgs)}/15 SVGs for '{head}'")

    if not svgs:
        typer.echo("No SVGs to validate.", err=True)
        raise typer.Exit(1)

    # Write the viewer HTML with injected SVG data
    viewer_dir = REPO_ROOT / "outputs" / ".validate"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    viewer_path = viewer_dir / "index.html"

    viewer_template = Path(__file__).parent.parent / "viewer" / "viewer.html"
    template = viewer_template.read_text()

    def safe_json(obj: object) -> str:
        return json.dumps(obj).replace("</", "<\\/")

    html = template.replace("/*SVGS_PLACEHOLDER*/", f"const SVGS = {safe_json(svgs)};")
    html = html.replace("/*HEAD_NAME_PLACEHOLDER*/", f"const HEAD_NAME = {json.dumps(head)};")
    viewer_path.write_text(html)

    # Serve it
    import http.server
    import threading
    import webbrowser

    if port == 0:
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(viewer_dir), **kw)
        def log_message(self, format, *args):
            pass  # silence logs

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    typer.echo(f"Viewer: {url}")
    typer.echo("Press Ctrl+C to stop.\n")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("\nStopped.")


@app.command()
def serve(
    port: int = typer.Option(7432, help="Server port"),
    host: str = typer.Option("127.0.0.1", help="Server host"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start the Voxhelm web studio (FastAPI server)."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.server.app import create_app
    import uvicorn

    app = create_app()
    typer.echo(f"\nVoxhelm Studio → http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)


# ── HTML writer for speak command ─────────────────────────────────────────────

def _write_speak_html(
    out_path: Path,
    svgs: dict[str, str],
    text: str,
    audio_b64: str,
    timeline: list[dict],
) -> None:
    """Write a self-contained HTML demo for a single sentence."""

    def safe_json(obj: object) -> str:
        return json.dumps(obj).replace("</", "<\\/")

    svgs_json = safe_json(svgs)
    timeline_json = safe_json(timeline)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Voxhelm Speak Demo</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#111;color:#eee;font-family:system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;padding:32px 20px}}
  h1{{font-size:18px;color:#fff;margin-bottom:4px}}
  .sub{{font-size:12px;color:#555;margin-bottom:20px}}
  .stage{{width:320px;height:320px;background:#1a1a1a;border-radius:18px;overflow:hidden;position:relative;border:1px solid #2a2a2a}}
  .stage svg{{width:100%;height:100%;position:absolute;top:0;left:0;display:none}}
  #blink-overlay{{display:block;width:100%;height:100%;position:absolute;top:0;left:0;pointer-events:none;z-index:10}}
  .vis-label{{margin-top:12px;font-size:26px;font-weight:700;color:#7cf;min-height:34px}}
  .controls{{display:flex;gap:10px;align-items:center;margin-top:14px}}
  .play-btn{{background:#2a6;color:#fff;border:none;padding:9px 26px;border-radius:8px;font-size:15px;cursor:pointer;font-weight:600}}
  .play-btn:hover{{background:#3b7}}
  .play-btn:disabled{{background:#333;cursor:default;color:#666}}
  .spd-btn{{background:#222;color:#888;border:1px solid #333;padding:6px 14px;border-radius:6px;font-size:13px;cursor:pointer}}
  .spd-btn.active{{background:#1a3050;border-color:#37f;color:#7af}}
  .progress{{width:360px;height:5px;background:#222;border-radius:3px;overflow:hidden;margin-top:14px}}
  .progress-bar{{height:100%;background:#2a6;width:0%}}
  .text-box{{max-width:440px;text-align:center;font-size:14px;color:#888;line-height:1.6;margin-top:14px}}
</style>
</head>
<body>
<h1>Voxhelm Speak Demo</h1>
<p class="sub">Audio-driven SVG viseme animation</p>

<div class="stage" id="stage">
  <svg id="blink-overlay" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
    <ellipse id="lid-l" cx="210" cy="240" rx="30" ry="0" fill="#F5C4A1" stroke="#3D2B1F" stroke-width="2"/>
    <ellipse id="lid-r" cx="302" cy="240" rx="30" ry="0" fill="#F5C4A1" stroke="#3D2B1F" stroke-width="2"/>
  </svg>
</div>

<div class="vis-label" id="vis-label">sil</div>

<div class="controls">
  <button class="play-btn" id="play-btn" onclick="playDemo()">&#9654; Play</button>
  <div style="display:flex;gap:4px">
    <button class="spd-btn" onclick="setSpeed(0.25)">0.25x</button>
    <button class="spd-btn" onclick="setSpeed(0.5)">0.5x</button>
    <button class="spd-btn active" id="spd-1" onclick="setSpeed(1)">1x</button>
  </div>
</div>

<div class="progress"><div class="progress-bar" id="pbar"></div></div>
<div class="text-box">{text}</div>

<audio id="audio" preload="auto" src="data:audio/mpeg;base64,{audio_b64}"></audio>

<script>
const SVGS = {svgs_json};
const TIMELINE = {timeline_json};

const stage = document.getElementById('stage');
const audio = document.getElementById('audio');
const playBtn = document.getElementById('play-btn');
const pbar = document.getElementById('pbar');
const visLabel = document.getElementById('vis-label');

const svgEls = {{}};
for (const [v, svg] of Object.entries(SVGS)) {{
  const tmp = document.createElement('div');
  tmp.innerHTML = svg;
  const el = tmp.firstElementChild;
  if (el) {{ el.id = 'svg-' + v; stage.appendChild(el); svgEls[v] = el; }}
}}

let curViseme = 'sil';
function showViseme(v) {{
  if (!svgEls[v]) v = 'sil';
  if (v === curViseme) return;
  if (svgEls[curViseme]) svgEls[curViseme].style.display = 'none';
  if (svgEls[v]) svgEls[v].style.display = 'block';
  curViseme = v;
  visLabel.textContent = v;
}}
if (svgEls['sil']) svgEls['sil'].style.display = 'block';

let curSpeed = 1;
function getVisemeAt(t) {{
  for (let i = 0; i < TIMELINE.length - 1; i++)
    if (t >= TIMELINE[i].t && t < TIMELINE[i+1].t) return TIMELINE[i].v;
  return 'sil';
}}

function tick() {{
  const t = audio.currentTime;
  pbar.style.width = (t / (audio.duration || 1) * 100) + '%';
  showViseme(getVisemeAt(t));
  if (!audio.paused && !audio.ended) requestAnimationFrame(tick);
  else if (audio.ended) {{ showViseme('sil'); playBtn.disabled = false; playBtn.textContent = '\\u25b6 Play again'; pbar.style.width = '100%'; }}
}}

function playDemo() {{
  audio.currentTime = 0; audio.playbackRate = curSpeed;
  playBtn.disabled = true; playBtn.textContent = '\\u23f8 Playing...';
  audio.play().then(() => requestAnimationFrame(tick));
}}

function setSpeed(s) {{
  curSpeed = s; audio.playbackRate = s;
  document.querySelectorAll('.spd-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.spd-btn').forEach(b => {{ if (b.textContent === s+'x') b.classList.add('active'); }});
}}

// Blink
const lidL = document.getElementById('lid-l'), lidR = document.getElementById('lid-r');
function setLids(ry) {{ if(lidL) lidL.setAttribute('ry',ry); if(lidR) lidR.setAttribute('ry',ry); }}
const BLINK_STEPS = [0,7,14,21,28,28,21,14,7,0];
function runBlink(cb) {{ BLINK_STEPS.forEach((ry,i) => setTimeout(() => setLids(ry), i*20)); setTimeout(cb, BLINK_STEPS.length*20); }}
function scheduleBlink() {{
  setTimeout(() => {{ runBlink(() => {{ if (Math.random()<0.25) setTimeout(() => runBlink(scheduleBlink), 250); else scheduleBlink(); }}); }}, 4000+Math.random()*5000);
}}
setTimeout(scheduleBlink, 1000+Math.random()*2000);
</script>
</body></html>"""

    out_path.write_text(html)
