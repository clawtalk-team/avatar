"""Voxhelm CLI — avatar generation and lip-sync toolkit.

Workflow:
  1. voxhelm generate-base  — create the reference frame (sil) for review
  2. voxhelm validate       — inspect the base in a web viewer
  3. voxhelm generate-visemes — generate the remaining 14 viseme frames
  4. voxhelm speak           — create an audio-driven demo
"""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
from pathlib import Path

import typer

from voxhelm import REPO_ROOT, load_env

app = typer.Typer(
    name="voxhelm",
    help="Avatar generation and audio-driven lip-sync toolkit.",
    no_args_is_help=True,
)

HEADS_DIR = REPO_ROOT / "outputs" / "heads"
ALL_VISEMES = [
    "sil", "PP", "FF", "TH", "dd", "kk", "CH", "SS",
    "nn", "RR", "aa", "E", "I", "O", "U",
]


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="  %(message)s",
        handlers=[logging.StreamHandler()],
    )


def _resolve_style_name(
    preset: str | None, prompt: str | None, name: str | None,
) -> tuple[str, str]:
    """Resolve style description and output name from preset or custom prompt."""
    from voxhelm.core.presets import PRESETS

    if preset:
        if preset not in PRESETS:
            typer.echo(f"Unknown preset: {preset}", err=True)
            raise typer.Exit(1)
        return PRESETS[preset], name or preset
    elif prompt:
        auto_name = re.sub(r"[^a-z0-9]+", "_", prompt[:40].lower()).strip("_")
        return prompt, name or auto_name
    else:
        typer.echo("Provide --prompt or --preset (or --list-presets to see options)", err=True)
        raise typer.Exit(1)


# ── Step 1: Generate base ──────────────────────────────────────────────────

@app.command("generate-base")
def generate_base(
    mode: str = typer.Option("svg", help="Generation mode: svg (cartoon) or photo (photorealistic)"),
    preset: str = typer.Option(None, help="Use a bundled character preset (svg mode)"),
    prompt: str = typer.Option(None, "--prompt", help="Character description prompt"),
    name: str = typer.Option(None, help="Output directory name"),
    list_presets: bool = typer.Option(False, "--list-presets", help="List available presets"),
    model: str = typer.Option("claude-opus-4-6", help="Claude model (svg mode only)"),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Step 1: Generate the base (sil) frame for a character.

    Creates a single reference frame for review before generating all 15 visemes.
    """
    _setup_logging(verbose)
    load_env()

    if mode not in ("svg", "photo"):
        typer.echo(f"Unknown mode: {mode}. Use 'svg' or 'photo'.", err=True)
        raise typer.Exit(1)

    if list_presets:
        from voxhelm.core.presets import PRESETS
        typer.echo("\nAvailable presets:\n")
        for k, v in PRESETS.items():
            typer.echo(f"  --preset {k}")
            typer.echo(f"    {v}\n")
        return

    resolved_style, resolved_name = _resolve_style_name(preset, prompt, name)
    out_root = REPO_ROOT / out

    def progress(viseme: str, idx: int, total: int, status: str) -> None:
        typer.echo(f"  [{idx+1:2d}/{total}] {viseme:4s}  {status}")

    if mode == "svg":
        from voxhelm.core.generator import generate_base as gen_base
        result = gen_base(
            style=resolved_style, name=resolved_name,
            model=model, out_root=out_root, on_progress=progress,
        )
    else:
        from voxhelm.core.photo_generator import generate_base as gen_base
        result = gen_base(
            style=resolved_style, name=resolved_name,
            out_root=out_root, on_progress=progress,
        )

    # Save metadata so generate-visemes knows the style/mode
    meta_path = Path(out_root) / resolved_name / ".voxhelm.json"
    meta = {"mode": mode, "style": resolved_style, "name": resolved_name, "model": model}
    meta_path.write_text(json.dumps(meta, indent=2))

    typer.echo(f"\nBase saved: {result}")
    typer.echo(f"\nReview, then run:  voxhelm generate-visemes --head {resolved_name}")

    # Open the gallery for review
    gallery = Path(out_root) / resolved_name / "gallery.html"
    if gallery.exists():
        subprocess.run(["open", str(gallery)], check=False)


# ── Step 2: Generate visemes ───────────────────────────────────────────────

@app.command("generate-visemes")
def generate_visemes_cmd(
    head: str = typer.Option(..., help="Head name (from generate-base)"),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    skip_existing: bool = typer.Option(True, help="Skip visemes that already exist"),
    no_blink: bool = typer.Option(False, "--no-blink", help="Skip blink frame (photo mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Step 2: Generate the remaining 14 viseme frames from an approved base.

    Reads the mode and style from the base generation metadata.
    """
    _setup_logging(verbose)
    load_env()

    out_root = REPO_ROOT / out
    head_dir = out_root / head

    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    # Load metadata from generate-base
    meta_path = head_dir / ".voxhelm.json"
    if not meta_path.exists():
        typer.echo(f"No metadata found at {meta_path}. Run generate-base first.", err=True)
        raise typer.Exit(1)

    meta = json.loads(meta_path.read_text())
    mode = meta["mode"]
    style = meta["style"]
    model = meta.get("model", "claude-opus-4-6")

    def progress(viseme: str, idx: int, total: int, status: str) -> None:
        typer.echo(f"  [{idx+1:2d}/{total}] {viseme:4s}  {status}")

    if mode == "svg":
        from voxhelm.core.generator import generate_visemes as gen_vis
        gallery = gen_vis(
            style=style, name=head, model=model,
            out_root=out_root, skip_existing=skip_existing,
            on_progress=progress,
        )
    else:
        from voxhelm.core.photo_generator import generate_visemes as gen_vis
        gallery = gen_vis(
            style=style, name=head,
            out_root=out_root, skip_existing=skip_existing,
            include_blink=not no_blink,
            on_progress=progress,
        )

    typer.echo(f"\nGallery: {gallery}")

    # Regenerate proof page with current assets
    proof = _write_proof_page(head_dir, head, style, mode)
    typer.echo(f"Proof: {proof}")
    subprocess.run(["open", str(proof)], check=False)


# ── Step 3: Generate animations ───────────────────────────────────────────

@app.command("generate-anims")
def generate_anims_cmd(
    head: str = typer.Option(..., help="Head name (directory in outputs/heads/)"),
    modes: str = typer.Option(
        "idle,listening,thinking",
        help="Comma-separated animation modes to generate",
    ),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip modes that already have MP4s"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate animation videos (idle/listening/thinking) for a head.

    Requires OPENROUTER_API_KEY. Each mode costs ~$0.20 via Veo 3.1 Lite.
    """
    import os
    _setup_logging(verbose)
    load_env()

    out_root = REPO_ROOT / out
    head_dir = out_root / head

    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        typer.echo("OPENROUTER_API_KEY not set", err=True)
        raise typer.Exit(1)

    from voxhelm.core.animations import AnimationMode, generate_anim_video

    requested = [m.strip() for m in modes.split(",")]
    anim_dir = head_dir / "anim"

    def progress(viseme: str, idx: int, total: int, status: str) -> None:
        typer.echo(f"  [{idx+1:2d}/{total}] {viseme:4s}  {status}")

    anim_total_cost = 0.0
    for mode_str in requested:
        try:
            anim_mode = AnimationMode(mode_str)
        except ValueError:
            typer.echo(f"Unknown mode: {mode_str}", err=True)
            continue

        if skip_existing and (anim_dir / f"{mode_str}.mp4").exists():
            typer.echo(f"\nSkipping {mode_str} (already exists)")
            continue

        typer.echo(f"\nGenerating {mode_str} animation...")
        try:
            result = generate_anim_video(
                name=head,
                mode=anim_mode,
                api_key=api_key,
                out_root=str(out_root),
                on_progress=progress,
            )
            cost = result.get("cost", 0) if isinstance(result, dict) else 0
            anim_total_cost += cost
            cost_str = f" (${cost:.4f})" if cost else ""
            typer.echo(f"  {mode_str} done.{cost_str}")
        except Exception as e:
            typer.echo(f"  {mode_str} failed: {e}", err=True)

    if anim_total_cost > 0:
        typer.echo(f"\nAnimation cost: ${anim_total_cost:.4f}")

    # Load metadata for proof page
    meta_path = head_dir / ".voxhelm.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        proof = _write_proof_page(head_dir, head, meta.get("style", ""), meta.get("mode", "photo"))
        typer.echo(f"Proof: {proof}")
        subprocess.run(["open", str(proof)], check=False)


# ── Proof page ────────────────────────────────────────────────────────────


def _write_proof_page(head_dir: Path, name: str, style: str, mode: str) -> Path:
    """Write a proof page with viseme grid, animation previews, and speak link."""

    # Build viseme thumbnail cards
    cards = []
    for v in ALL_VISEMES:
        if mode == "svg":
            svg_file = head_dir / f"{v}.svg"
            if svg_file.exists():
                svg_content = svg_file.read_text()
                cards.append(
                    f'<div class="card">'
                    f'<div class="label">{v}</div>'
                    f'<div class="svg-wrap">{svg_content}</div>'
                    f'</div>'
                )
            else:
                cards.append(
                    f'<div class="card"><div class="label">{v}</div>'
                    f'<p style="color:#f66">missing</p></div>'
                )
        else:
            png_file = head_dir / f"{v}.png"
            if png_file.exists():
                b64 = base64.b64encode(png_file.read_bytes()).decode()
                cards.append(
                    f'<div class="card">'
                    f'<div class="label">{v}</div>'
                    f'<img src="data:image/png;base64,{b64}" alt="{v}"/>'
                    f'</div>'
                )
            else:
                cards.append(
                    f'<div class="card"><div class="label">{v}</div>'
                    f'<p style="color:#f66">missing</p></div>'
                )

    # Build animation preview section
    anim_dir = head_dir / "anim"
    anim_cards = []
    for anim_mode in ("idle", "listening", "thinking"):
        mp4 = anim_dir / f"{anim_mode}.mp4"
        if mp4.exists():
            b64 = base64.b64encode(mp4.read_bytes()).decode()
            anim_cards.append(
                f'<div class="anim-card">'
                f'<div class="label">{anim_mode}</div>'
                f'<video autoplay loop muted playsinline '
                f'src="data:video/mp4;base64,{b64}" '
                f'style="width:200px;height:200px;border-radius:8px;object-fit:cover">'
                f'</video></div>'
            )
        else:
            anim_cards.append(
                f'<div class="anim-card">'
                f'<div class="label">{anim_mode}</div>'
                f'<p style="color:#888">not generated</p></div>'
            )

    anim_section = ""
    anim_count = sum(1 for m in ("idle", "listening", "thinking")
                     if (anim_dir / f"{m}.mp4").exists())
    if anim_cards:
        cost_note = ""
        if anim_count > 0:
            cost_note = (
                f'<p class="cost">Generated {anim_count} &times; Veo 3.1 Lite video via OpenRouter '
                f'&mdash; ~$0.20 per mode, ~$0.60 total for all 3.</p>'
            )
        anim_section = f"""
  <h2>Animation Modes</h2>
  <div class="grid">{"".join(anim_cards)}</div>
  {cost_note}"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>{name} — Proof</title>
<style>
  body{{background:#1a1a1a;color:#eee;font-family:system-ui,sans-serif;padding:20px;max-width:1200px;margin:0 auto}}
  h1{{color:#fff;margin-bottom:4px}}
  h2{{color:#ddd;margin-top:32px;margin-bottom:12px;border-bottom:1px solid #333;padding-bottom:8px}}
  p.sub{{color:#888;margin-top:0;margin-bottom:20px;font-size:14px}}
  .grid{{display:flex;flex-wrap:wrap;gap:16px}}
  .card,.anim-card{{background:#2a2a2a;border-radius:12px;padding:12px;text-align:center;width:220px}}
  .label{{font-size:13px;font-weight:700;color:#7cf;margin:0 0 8px}}
  .card img,.svg-wrap svg{{width:200px;height:200px;display:block;margin:0 auto;border-radius:8px;object-fit:cover}}
  .cost{{color:#888;font-size:12px;margin-top:12px;font-style:italic}}
  .next-steps{{background:#222;border:1px solid #333;border-radius:8px;padding:16px;margin-top:8px}}
  .next-steps h3{{margin:0 0 12px;color:#fff;font-size:15px}}
  .next-steps li{{margin:6px 0;line-height:1.5}}
  .next-steps a{{color:#7cf}}
  code{{background:#333;padding:2px 6px;border-radius:4px;font-size:13px}}
</style></head>
<body>
  <h1>{name}</h1>
  <p class="sub">Style: {style} &mdash; Mode: {mode}</p>

  <h2>Visemes</h2>
  <div class="grid">{"".join(cards)}</div>
  {anim_section}

  <h2>Next Steps</h2>
  <div class="next-steps">
    <h3>Speech Test</h3>
    <ul>
      <li><strong>Web studio:</strong> Run <code>voxhelm serve</code> then open
        <a href="http://localhost:7432">localhost:7432</a> &mdash; select <em>{name}</em>
        from the sidebar to test speech with the Speak Demo.</li>
      <li><strong>CLI:</strong> <code>voxhelm speak --head {name} --text "Hello, I am {name}."</code></li>
    </ul>
    <h3>Flutter Integration</h3>
    <ul>
      <li><strong>Export to app:</strong> <code>voxhelm export --head {name}</code>
        &mdash; copies viseme assets to <code>../flutter-app/assets/heads/{name}/</code>
        and registers in <code>pubspec.yaml</code></li>
      <li><strong>Or load from API:</strong> <code>VisemeSet.fromUrl('http://host:7432/api/head/{name}/svgs')</code></li>
      <li>See <a href="file://{str(REPO_ROOT / 'docs' / 'flutter_integration.md')}">docs/flutter_integration.md</a>
        for full guide.</li>
    </ul>
  </div>
</body></html>"""

    proof_path = head_dir / "proof.html"
    proof_path.write_text(html)
    return proof_path


# ── One-shot generate (both steps) ────────────────────────────────────────

@app.command()
def generate(
    mode: str = typer.Option("svg", help="Generation mode: svg (cartoon) or photo (photorealistic)"),
    preset: str = typer.Option(None, help="Use a bundled character preset"),
    prompt: str = typer.Option(None, "--prompt", help="Character description prompt"),
    name: str = typer.Option(None, help="Output directory name"),
    list_presets: bool = typer.Option(False, "--list-presets", help="List available presets"),
    model: str = typer.Option("claude-opus-4-6", help="Claude model (svg mode only)"),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip existing assets"),
    no_blink: bool = typer.Option(False, "--no-blink", help="Skip blink frame (photo mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate all 15 viseme assets in one shot (base + visemes).

    For more control, use generate-base + generate-visemes instead.
    """
    _setup_logging(verbose)
    load_env()

    if mode not in ("svg", "photo"):
        typer.echo(f"Unknown mode: {mode}. Use 'svg' or 'photo'.", err=True)
        raise typer.Exit(1)

    if list_presets:
        from voxhelm.core.presets import PRESETS
        typer.echo("\nAvailable presets:\n")
        for k, v in PRESETS.items():
            typer.echo(f"  --preset {k}")
            typer.echo(f"    {v}\n")
        return

    resolved_style, resolved_name = _resolve_style_name(preset, prompt, name)
    out_root = REPO_ROOT / out

    # Save metadata
    head_dir = out_root / resolved_name
    head_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mode": mode, "style": resolved_style, "name": resolved_name, "model": model}
    (head_dir / ".voxhelm.json").write_text(json.dumps(meta, indent=2))

    def progress(viseme: str, idx: int, total: int, status: str) -> None:
        typer.echo(f"  [{idx+1:2d}/{total}] {viseme:4s}  {status}")

    if mode == "svg":
        from voxhelm.core.generator import generate as gen
        gallery = gen(
            style=resolved_style, name=resolved_name, model=model,
            out_root=out_root, skip_existing=skip_existing,
            on_progress=progress,
        )
    else:
        from voxhelm.core.photo_generator import generate as gen
        gallery = gen(
            style=resolved_style, name=resolved_name,
            out_root=out_root, skip_existing=skip_existing,
            include_blink=not no_blink, on_progress=progress,
        )

    typer.echo(f"\nVisemes done: {gallery}")

    # Step 3: Generate animation videos (idle/listening/thinking)
    import os
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        from voxhelm.core.animations import AnimationMode, generate_anim_video

        anim_total_cost = 0.0
        for anim_mode in AnimationMode:
            typer.echo(f"\nGenerating {anim_mode.value} animation...")
            try:
                result = generate_anim_video(
                    name=resolved_name,
                    mode=anim_mode,
                    api_key=api_key,
                    out_root=str(out_root),
                    on_progress=progress,
                )
                cost = result.get("cost", 0) if isinstance(result, dict) else 0
                anim_total_cost += cost
                cost_str = f" (${cost:.4f})" if cost else ""
                typer.echo(f"  {anim_mode.value} animation done.{cost_str}")
            except Exception as e:
                typer.echo(f"  {anim_mode.value} animation failed: {e}", err=True)
        if anim_total_cost > 0:
            typer.echo(f"\nAnimation cost: ${anim_total_cost:.4f}")
    else:
        typer.echo("\nSkipping animation generation (no OPENROUTER_API_KEY).")

    # Step 4: Write and open proof page
    head_dir = out_root / resolved_name
    proof = _write_proof_page(head_dir, resolved_name, resolved_style, mode)
    typer.echo(f"\nProof: {proof}")
    subprocess.run(["open", str(proof)], check=False)


# ── Speak ──────────────────────────────────────────────────────────────────

@app.command()
def speak(
    head: str = typer.Option(..., help="Head name (directory in outputs/heads/)"),
    text: str = typer.Option(..., help="Text to speak"),
    out: str = typer.Option(None, help="Output HTML path"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate TTS audio with viseme timeline and write a playback demo."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.core.audio import deepgram_tts, deepgram_stt_words
    from voxhelm.core.timeline import words_to_timeline

    head_dir = HEADS_DIR / head
    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    # Detect mode from file types present
    has_svgs = any((head_dir / f"{v}.svg").exists() for v in ["sil", "PP", "aa"])
    has_pngs = any((head_dir / f"{v}.png").exists() for v in ["sil", "PP", "aa"])

    if has_svgs:
        from voxhelm.core.generator import load_svgs
        assets = load_svgs(head_dir)
        asset_mode = "svg"
    elif has_pngs:
        assets = _load_png_assets(head_dir)
        asset_mode = "photo"
    else:
        typer.echo(f"No SVG or PNG viseme assets found in {head_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loaded {len(assets)} {asset_mode} assets for '{head}'")

    audio_bytes = deepgram_tts(text)
    words = deepgram_stt_words(audio_bytes)
    timeline = words_to_timeline(words)
    typer.echo(f"Timeline: {len(timeline)} events")

    audio_b64 = base64.b64encode(audio_bytes).decode()
    out_path = Path(out) if out else REPO_ROOT / "outputs" / "speak_demo.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if asset_mode == "svg":
        _write_speak_html_svg(out_path, assets, text, audio_b64, timeline)
    else:
        _write_speak_html_photo(out_path, assets, text, audio_b64, timeline)

    typer.echo(f"\nDemo: {out_path}")
    subprocess.run(["open", str(out_path)], check=False)


# ── Export ─────────────────────────────────────────────────────────────────

@app.command()
def export(
    head: str = typer.Option(..., help="Head name (directory in outputs/heads/)"),
    target: str = typer.Option(
        None, help="Target Flutter app directory (default: ../flutter-app)"
    ),
    out: str = typer.Option("outputs/heads", help="Root output directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Package a generated head into a Flutter app's assets.

    Copies viseme files (SVG or PNG) to the target app's
    assets/heads/{name}/ directory and registers the asset path
    in pubspec.yaml if not already present.
    """
    import shutil
    import yaml

    _setup_logging(verbose)

    head_dir = REPO_ROOT / out / head
    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    # Detect mode
    has_svgs = any((head_dir / f"{v}.svg").exists() for v in ALL_VISEMES)
    has_pngs = any((head_dir / f"{v}.png").exists() for v in ALL_VISEMES)
    if not has_svgs and not has_pngs:
        typer.echo(f"No viseme assets found in {head_dir}", err=True)
        raise typer.Exit(1)
    ext = "svg" if has_svgs else "png"

    # Resolve target Flutter app
    target_root = Path(target) if target else REPO_ROOT.parent / "flutter-app"
    pubspec_path = target_root / "pubspec.yaml"
    if not pubspec_path.exists():
        typer.echo(f"No pubspec.yaml at {target_root} — is this a Flutter app?", err=True)
        raise typer.Exit(1)

    # Copy viseme files
    dest_dir = target_root / "assets" / "heads" / head
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for v in ALL_VISEMES:
        src = head_dir / f"{v}.{ext}"
        if src.exists():
            shutil.copy2(src, dest_dir / f"{v}.{ext}")
            copied += 1

    # Also copy extras (blink, brows_up) if they exist
    for extra in ("blink", "brows_up"):
        src = head_dir / f"{extra}.{ext}"
        if src.exists():
            shutil.copy2(src, dest_dir / f"{extra}.{ext}")
            copied += 1

    typer.echo(f"Copied {copied} files to {dest_dir}")

    # Register in pubspec.yaml if needed
    asset_entry = f"assets/heads/{head}/"
    pubspec_text = pubspec_path.read_text()
    pubspec = yaml.safe_load(pubspec_text)

    flutter_assets = (
        pubspec.get("flutter", {}).get("assets", []) if pubspec.get("flutter") else []
    )
    if asset_entry not in flutter_assets:
        # Insert the asset entry after the last heads/ entry, or at end of assets
        marker = "    - assets/heads/"
        lines = pubspec_text.splitlines(keepends=True)
        insert_idx = None
        for i, line in enumerate(lines):
            if marker in line:
                insert_idx = i + 1
        if insert_idx is not None:
            lines.insert(insert_idx, f"    - {asset_entry}\n")
            pubspec_path.write_text("".join(lines))
            typer.echo(f"Added '{asset_entry}' to {pubspec_path}")
        else:
            typer.echo(
                f"Could not find assets/heads/ section in pubspec.yaml — "
                f"add manually: '    - {asset_entry}'",
                err=True,
            )
    else:
        typer.echo(f"Asset entry '{asset_entry}' already in pubspec.yaml")


# ── Validate ───────────────────────────────────────────────────────────────

@app.command()
def validate(
    head: str = typer.Option(..., help="Head name to validate"),
    port: int = typer.Option(0, help="Port for web viewer (0=auto)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Launch a web viewer to validate generated assets."""
    _setup_logging(verbose)
    load_env()

    from voxhelm.core.visemes import ALL_VISEMES

    head_dir = HEADS_DIR / head
    if not head_dir.exists():
        typer.echo(f"Head not found: {head_dir}", err=True)
        raise typer.Exit(1)

    has_svgs = any((head_dir / f"{v}.svg").exists() for v in ALL_VISEMES)
    has_pngs = any((head_dir / f"{v}.png").exists() for v in ALL_VISEMES)

    if has_svgs:
        from voxhelm.core.generator import load_svgs
        assets = load_svgs(head_dir)
        asset_mode = "svg"
    elif has_pngs:
        assets = _load_png_assets(head_dir)
        asset_mode = "photo"
    else:
        typer.echo("No viseme assets found.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loaded {len(assets)}/15 {asset_mode} assets for '{head}'")

    viewer_dir = REPO_ROOT / "outputs" / ".validate"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    viewer_path = viewer_dir / "index.html"

    viewer_template = Path(__file__).parent.parent / "viewer" / "viewer.html"
    template = viewer_template.read_text()

    def safe_json(obj: object) -> str:
        return json.dumps(obj).replace("</", "<\\/")

    html = template.replace("/*SVGS_PLACEHOLDER*/", f"const SVGS = {safe_json(assets)};")
    html = html.replace("/*HEAD_NAME_PLACEHOLDER*/", f"const HEAD_NAME = {json.dumps(head)};")
    html = html.replace("/*MODE_PLACEHOLDER*/", f"const ASSET_MODE = {json.dumps(asset_mode)};")
    viewer_path.write_text(html)

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
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    typer.echo(f"Viewer: {url}")
    typer.echo("Press Ctrl+C to stop.\n")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("\nStopped.")


# ── Serve ──────────────────────────────────────────────────────────────────

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

    _app = create_app()
    typer.echo(f"\nVoxhelm Studio → http://{host}:{port}\n")
    uvicorn.run(_app, host=host, port=port)


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_png_assets(head_dir: Path) -> dict[str, str]:
    """Load PNG viseme files as base64 data URI strings."""
    from voxhelm.core.visemes import ALL_VISEMES
    assets = {}
    for v in ALL_VISEMES:
        f = head_dir / f"{v}.png"
        if f.exists():
            b64 = base64.b64encode(f.read_bytes()).decode()
            assets[v] = f"data:image/png;base64,{b64}"
    return assets


def _write_speak_html_svg(
    out_path: Path, svgs: dict[str, str], text: str,
    audio_b64: str, timeline: list[dict],
) -> None:
    """Write a self-contained SVG speak demo."""
    def safe_json(obj: object) -> str:
        return json.dumps(obj).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><title>Voxhelm Speak Demo</title>
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
  .play-btn:hover{{background:#3b7}} .play-btn:disabled{{background:#333;cursor:default;color:#666}}
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
    <button class="spd-btn active" onclick="setSpeed(1)">1x</button>
  </div>
</div>
<div class="progress"><div class="progress-bar" id="pbar"></div></div>
<div class="text-box">{text}</div>
<audio id="audio" preload="auto" src="data:audio/mpeg;base64,{audio_b64}"></audio>
<script>
const SVGS={safe_json(svgs)},TIMELINE={safe_json(timeline)};
const stage=document.getElementById('stage'),audio=document.getElementById('audio'),
  playBtn=document.getElementById('play-btn'),pbar=document.getElementById('pbar'),
  visLabel=document.getElementById('vis-label');
const svgEls={{}};
for(const[v,svg]of Object.entries(SVGS)){{const d=document.createElement('div');d.innerHTML=svg;const e=d.firstElementChild;if(e){{e.id='svg-'+v;stage.appendChild(e);svgEls[v]=e}}}}
let cur='sil';
function show(v){{if(!svgEls[v])v='sil';if(v===cur)return;if(svgEls[cur])svgEls[cur].style.display='none';if(svgEls[v])svgEls[v].style.display='block';cur=v;visLabel.textContent=v}}
if(svgEls['sil'])svgEls['sil'].style.display='block';
let spd=1;
function vis(t){{for(let i=0;i<TIMELINE.length-1;i++)if(t>=TIMELINE[i].t&&t<TIMELINE[i+1].t)return TIMELINE[i].v;return'sil'}}
function tick(){{const t=audio.currentTime;pbar.style.width=(t/(audio.duration||1)*100)+'%';show(vis(t));if(!audio.paused&&!audio.ended)requestAnimationFrame(tick);else if(audio.ended){{show('sil');playBtn.disabled=false;playBtn.textContent='\\u25b6 Play again';pbar.style.width='100%'}}}}
function playDemo(){{audio.currentTime=0;audio.playbackRate=spd;playBtn.disabled=true;playBtn.textContent='\\u23f8 Playing...';audio.play().then(()=>requestAnimationFrame(tick))}}
function setSpeed(s){{spd=s;audio.playbackRate=s;document.querySelectorAll('.spd-btn').forEach(b=>b.classList.remove('active'));document.querySelectorAll('.spd-btn').forEach(b=>{{if(b.textContent===s+'x')b.classList.add('active')}})}}
const lidL=document.getElementById('lid-l'),lidR=document.getElementById('lid-r');
function setLids(ry){{if(lidL)lidL.setAttribute('ry',ry);if(lidR)lidR.setAttribute('ry',ry)}}
const BS=[0,7,14,21,28,28,21,14,7,0];
function blink(cb){{BS.forEach((ry,i)=>setTimeout(()=>setLids(ry),i*20));setTimeout(cb,BS.length*20)}}
function sched(){{setTimeout(()=>{{blink(()=>{{if(Math.random()<0.25)setTimeout(()=>blink(sched),250);else sched()}})}},4000+Math.random()*5000)}}
setTimeout(sched,1000+Math.random()*2000);
</script>
</body></html>"""
    out_path.write_text(html)


def _write_speak_html_photo(
    out_path: Path, assets: dict[str, str], text: str,
    audio_b64: str, timeline: list[dict],
) -> None:
    """Write a self-contained photo speak demo."""
    def safe_json(obj: object) -> str:
        return json.dumps(obj).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><title>Voxhelm Speak Demo (Photo)</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#111;color:#eee;font-family:system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;padding:32px 20px}}
  h1{{font-size:18px;color:#fff;margin-bottom:4px}}
  .sub{{font-size:12px;color:#555;margin-bottom:20px}}
  .stage{{width:320px;height:320px;background:#1a1a1a;border-radius:18px;overflow:hidden;position:relative;border:1px solid #2a2a2a}}
  .stage img{{width:100%;height:100%;position:absolute;top:0;left:0;display:none;object-fit:cover}}
  .vis-label{{margin-top:12px;font-size:26px;font-weight:700;color:#7cf;min-height:34px}}
  .controls{{display:flex;gap:10px;align-items:center;margin-top:14px}}
  .play-btn{{background:#2a6;color:#fff;border:none;padding:9px 26px;border-radius:8px;font-size:15px;cursor:pointer;font-weight:600}}
  .play-btn:hover{{background:#3b7}} .play-btn:disabled{{background:#333;cursor:default;color:#666}}
  .spd-btn{{background:#222;color:#888;border:1px solid #333;padding:6px 14px;border-radius:6px;font-size:13px;cursor:pointer}}
  .spd-btn.active{{background:#1a3050;border-color:#37f;color:#7af}}
  .progress{{width:360px;height:5px;background:#222;border-radius:3px;overflow:hidden;margin-top:14px}}
  .progress-bar{{height:100%;background:#2a6;width:0%}}
  .text-box{{max-width:440px;text-align:center;font-size:14px;color:#888;line-height:1.6;margin-top:14px}}
</style>
</head>
<body>
<h1>Voxhelm Speak Demo</h1>
<p class="sub">Audio-driven photorealistic viseme animation</p>
<div class="stage" id="stage"></div>
<div class="vis-label" id="vis-label">sil</div>
<div class="controls">
  <button class="play-btn" id="play-btn" onclick="playDemo()">&#9654; Play</button>
  <div style="display:flex;gap:4px">
    <button class="spd-btn" onclick="setSpeed(0.25)">0.25x</button>
    <button class="spd-btn" onclick="setSpeed(0.5)">0.5x</button>
    <button class="spd-btn active" onclick="setSpeed(1)">1x</button>
  </div>
</div>
<div class="progress"><div class="progress-bar" id="pbar"></div></div>
<div class="text-box">{text}</div>
<audio id="audio" preload="auto" src="data:audio/mpeg;base64,{audio_b64}"></audio>
<script>
const ASSETS={safe_json(assets)},TIMELINE={safe_json(timeline)};
const stage=document.getElementById('stage'),audio=document.getElementById('audio'),
  playBtn=document.getElementById('play-btn'),pbar=document.getElementById('pbar'),
  visLabel=document.getElementById('vis-label');
const imgEls={{}};
for(const[v,src]of Object.entries(ASSETS)){{const img=document.createElement('img');img.src=src;img.id='img-'+v;stage.appendChild(img);imgEls[v]=img}}
let cur='sil';
function show(v){{if(!imgEls[v])v='sil';if(v===cur)return;if(imgEls[cur])imgEls[cur].style.display='none';if(imgEls[v])imgEls[v].style.display='block';cur=v;visLabel.textContent=v}}
if(imgEls['sil'])imgEls['sil'].style.display='block';
let spd=1;
function vis(t){{for(let i=0;i<TIMELINE.length-1;i++)if(t>=TIMELINE[i].t&&t<TIMELINE[i+1].t)return TIMELINE[i].v;return'sil'}}
function tick(){{const t=audio.currentTime;pbar.style.width=(t/(audio.duration||1)*100)+'%';show(vis(t));if(!audio.paused&&!audio.ended)requestAnimationFrame(tick);else if(audio.ended){{show('sil');playBtn.disabled=false;playBtn.textContent='\\u25b6 Play again';pbar.style.width='100%'}}}}
function playDemo(){{audio.currentTime=0;audio.playbackRate=spd;playBtn.disabled=true;playBtn.textContent='\\u23f8 Playing...';audio.play().then(()=>requestAnimationFrame(tick))}}
function setSpeed(s){{spd=s;audio.playbackRate=s;document.querySelectorAll('.spd-btn').forEach(b=>b.classList.remove('active'));document.querySelectorAll('.spd-btn').forEach(b=>{{if(b.textContent===s+'x')b.classList.add('active')}})}}
</script>
</body></html>"""
    out_path.write_text(html)
