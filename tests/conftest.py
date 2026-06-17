"""Shared test fixtures for voxhelm test suite."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.fixtures.samples import SAMPLE_SVG, SAMPLE_MOUTH, MINIMAL_PNG, FAKE_MP3, FAKE_WORDS


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
    # Copy the real webapp so smoke tests can verify its content
    import voxhelm
    real_webapp = Path(voxhelm.__file__).parent.parent / "webapp" / "index.html"
    if real_webapp.exists():
        (tmp_path / "webapp" / "index.html").write_text(real_webapp.read_text())
    else:
        (tmp_path / "webapp" / "index.html").write_text("<html><body>Voxhelm Studio</body></html>")
    return tmp_path


# ── Mock LLM client ────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_client():
    """LLMClient that returns structured SVG for base or mouth fragment for visemes."""
    from voxhelm.core.api_client import LLMClient, LLMResponse

    def _smart_generate(system: str, prompt: str, max_tokens: int = 4096) -> LLMResponse:
        # Return mouth fragment for mouth-specific prompts, full SVG otherwise
        if "mouth" in system.lower() and "inside" in system.lower():
            return LLMResponse(text=SAMPLE_MOUTH, output_tokens=50)
        return LLMResponse(text=SAMPLE_SVG, output_tokens=100)

    client = MagicMock(spec=LLMClient)
    client.generate.side_effect = _smart_generate
    return client


# ── Monkeypatch helpers ─────────────────────────────────────────────────────

@pytest.fixture
def mock_photo_generate(monkeypatch):
    """Patch _generate_image to return a 1x1 PNG with mock usage."""
    monkeypatch.setattr(
        "voxhelm.core.photo_generator._generate_image",
        lambda *a, **kw: (MINIMAL_PNG, {"prompt_tokens": 100, "completion_tokens": 50, "total_cost": 0.01}),
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
