"""Shared test fixtures for voxhelm test suite."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.fixtures.samples import SAMPLE_SVG, MINIMAL_PNG, FAKE_MP3, FAKE_WORDS


# ── Directory fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_heads_dir(tmp_path):
    """Temporary heads directory for test isolation."""
    heads = tmp_path / "outputs" / "heads"
    heads.mkdir(parents=True)
    return heads


@pytest.fixture
def tmp_repo_root(tmp_path):
    """Temporary repo root with outputs/ structure."""
    (tmp_path / "outputs" / "heads").mkdir(parents=True)
    (tmp_path / "outputs" / "webapp_cache").mkdir(parents=True)
    (tmp_path / "webapp").mkdir(parents=True)
    # Create a minimal index.html so the server can serve /
    (tmp_path / "webapp" / "index.html").write_text("<html><body>Voxhelm</body></html>")
    return tmp_path


# ── Mock LLM client ────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_client():
    """LLMClient that returns a minimal valid SVG."""
    from voxhelm.core.api_client import LLMClient, LLMResponse
    client = MagicMock(spec=LLMClient)
    client.generate.return_value = LLMResponse(text=SAMPLE_SVG, output_tokens=100)
    return client


# ── Monkeypatch helpers ─────────────────────────────────────────────────────

@pytest.fixture
def mock_photo_generate(monkeypatch):
    """Patch _generate_image to return a 1x1 PNG."""
    monkeypatch.setattr(
        "voxhelm.core.photo_generator._generate_image",
        lambda *a, **kw: MINIMAL_PNG,
    )


@pytest.fixture
def mock_openrouter_key(monkeypatch):
    """Set a fake OpenRouter API key."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake-test-key")


@pytest.fixture
def mock_deepgram(monkeypatch):
    """Mock Deepgram TTS and STT."""
    monkeypatch.setattr("voxhelm.core.audio.deepgram_tts", lambda *a, **kw: FAKE_MP3)
    monkeypatch.setattr("voxhelm.core.audio.deepgram_stt_words", lambda *a, **kw: FAKE_WORDS)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-deepgram-key")


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Prevent CLI from opening browsers."""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)


# ── Populated head directories ─────────────────────────────────────────────

@pytest.fixture
def svg_head(tmp_heads_dir, mock_llm_client):
    """A head directory with all 15 SVG visemes."""
    from voxhelm.core.generator import generate
    generate(
        style="test character", name="test_svg",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    return tmp_heads_dir / "test_svg"


@pytest.fixture
def photo_head(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    """A head directory with all 15 PNG visemes."""
    from voxhelm.core.photo_generator import generate
    generate(
        style="test character", name="test_photo",
        out_root=tmp_heads_dir,
    )
    return tmp_heads_dir / "test_photo"


# ── FastAPI test client ─────────────────────────────────────────────────────

@pytest.fixture
def api_client(tmp_repo_root, mock_llm_client, mock_photo_generate,
               mock_openrouter_key, mock_deepgram, monkeypatch):
    """Starlette TestClient for testing the FastAPI app (sync wrapper over async)."""
    import voxhelm
    monkeypatch.setattr(voxhelm, "REPO_ROOT", tmp_repo_root)

    # Mock get_llm_client at both source and import locations
    mock_factory = lambda *a, **kw: mock_llm_client
    monkeypatch.setattr("voxhelm.core.api_client.get_llm_client", mock_factory)
    monkeypatch.setattr("voxhelm.core.generator.get_llm_client", mock_factory)

    from voxhelm.server.app import create_app
    from starlette.testclient import TestClient
    app = create_app()
    return TestClient(app)
