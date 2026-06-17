"""Tests for the Voxhelm CLI commands via typer CliRunner."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from voxhelm.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_all(tmp_path, mock_llm_client, mock_photo_generate,
               mock_openrouter_key, mock_deepgram, mock_subprocess, monkeypatch):
    """Patch REPO_ROOT, LLM client, and env for all CLI tests."""
    import voxhelm
    (tmp_path / "outputs" / "heads").mkdir(parents=True)
    monkeypatch.setattr(voxhelm, "REPO_ROOT", tmp_path)
    # Must patch at both the source AND where it's imported
    mock_factory = lambda *a, **kw: mock_llm_client
    monkeypatch.setattr("voxhelm.core.api_client.get_llm_client", mock_factory)
    monkeypatch.setattr("voxhelm.core.generator.get_llm_client", mock_factory)
    yield tmp_path


def _heads_dir(tmp_path):
    return tmp_path / "outputs" / "heads"


# ── Help ───────────────────────────────────────────────────────────────────

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate-base" in result.output
    assert "generate-visemes" in result.output
    assert "speak" in result.output


# ── List presets ───────────────────────────────────────────────────────────

def test_list_presets():
    result = runner.invoke(app, ["generate-base", "--list-presets"])
    assert result.exit_code == 0
    assert "young_woman" in result.output
    assert "older_man" in result.output


# ── Generate base ──────────────────────────────────────────────────────────

def test_generate_base_preset(_patch_all):
    tmp_path = _patch_all
    result = runner.invoke(app, [
        "generate-base", "--preset", "young_woman",
        "--out", str(_heads_dir(tmp_path)),
    ])
    assert result.exit_code == 0
    assert (_heads_dir(tmp_path) / "young_woman" / "sil.svg").exists()


def test_generate_base_custom_prompt(_patch_all):
    tmp_path = _patch_all
    result = runner.invoke(app, [
        "generate-base", "--prompt", "robot, teal accents", "--name", "bot",
        "--out", str(_heads_dir(tmp_path)),
    ])
    assert result.exit_code == 0
    assert (_heads_dir(tmp_path) / "bot" / "sil.svg").exists()


def test_generate_base_photo(_patch_all):
    tmp_path = _patch_all
    result = runner.invoke(app, [
        "generate-base", "--mode", "photo",
        "--prompt", "woman, 30s", "--name", "photo_cli",
        "--out", str(_heads_dir(tmp_path)),
    ])
    assert result.exit_code == 0
    assert (_heads_dir(tmp_path) / "photo_cli" / "base.png").exists()


def test_generate_base_no_input():
    result = runner.invoke(app, ["generate-base"])
    assert result.exit_code != 0


def test_generate_base_bad_mode():
    result = runner.invoke(app, [
        "generate-base", "--mode", "invalid", "--prompt", "test",
    ])
    assert result.exit_code != 0


# ── Generate visemes ───────────────────────────────────────────────────────

def test_generate_visemes_svg(_patch_all):
    tmp_path = _patch_all
    heads = _heads_dir(tmp_path)
    # Create base first
    runner.invoke(app, [
        "generate-base", "--preset", "young_man", "--out", str(heads),
    ])
    # Generate visemes
    result = runner.invoke(app, [
        "generate-visemes", "--head", "young_man", "--out", str(heads),
    ])
    assert result.exit_code == 0
    svg_count = len(list((heads / "young_man").glob("*.svg")))
    assert svg_count == 15


def test_generate_visemes_missing_head(_patch_all):
    tmp_path = _patch_all
    result = runner.invoke(app, [
        "generate-visemes", "--head", "nonexistent",
        "--out", str(_heads_dir(tmp_path)),
    ])
    assert result.exit_code != 0


# ── One-shot generate ──────────────────────────────────────────────────────

def test_generate_full_svg(_patch_all):
    tmp_path = _patch_all
    heads = _heads_dir(tmp_path)
    result = runner.invoke(app, [
        "generate", "--preset", "young_woman", "--out", str(heads),
    ])
    assert result.exit_code == 0
    svg_count = len(list((heads / "young_woman").glob("*.svg")))
    assert svg_count == 15


def test_generate_full_photo(_patch_all):
    tmp_path = _patch_all
    heads = _heads_dir(tmp_path)
    result = runner.invoke(app, [
        "generate", "--mode", "photo",
        "--prompt", "test person", "--name", "photo_full",
        "--out", str(heads),
    ])
    assert result.exit_code == 0
    png_count = len([f for f in (heads / "photo_full").glob("*.png") if f.name not in ("base.png", "blink.png", "brows_up.png")])
    assert png_count == 15


# ── Speak ──────────────────────────────────────────────────────────────────

def test_speak_svg(_patch_all):
    tmp_path = _patch_all
    heads = _heads_dir(tmp_path)
    # Generate a head first
    runner.invoke(app, [
        "generate", "--preset", "young_woman", "--out", str(heads),
    ])
    result = runner.invoke(app, [
        "speak", "--head", "young_woman", "--text", "hello world",
        "--out", str(tmp_path / "demo.html"),
    ])
    assert result.exit_code == 0
    assert (tmp_path / "demo.html").exists()


def test_speak_missing_head(_patch_all):
    result = runner.invoke(app, [
        "speak", "--head", "nonexistent", "--text", "hello",
    ])
    assert result.exit_code != 0
