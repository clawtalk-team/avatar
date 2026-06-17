"""Tests for voxhelm.core.generator (SVG generation with mocked LLM)."""

import json
import pytest
from pathlib import Path

from voxhelm.core.generator import (
    generate_base, generate_visemes, generate, load_svgs,
    build_prompt, _clean_svg, write_gallery,
)
from voxhelm.core.visemes import ALL_VISEMES
from tests.fixtures.samples import SAMPLE_SVG


def test_generate_base_creates_sil(tmp_heads_dir, mock_llm_client):
    result = generate_base(
        style="test char", name="base_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    assert result.exists()
    assert result.name == "sil.svg"
    assert (tmp_heads_dir / "base_test" / "sil.svg").exists()


def test_generate_base_creates_gallery(tmp_heads_dir, mock_llm_client):
    generate_base(
        style="test char", name="gallery_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    assert (tmp_heads_dir / "gallery_test" / "gallery.html").exists()


def test_generate_visemes_creates_14(tmp_heads_dir, mock_llm_client):
    # First create the base
    generate_base(
        style="test char", name="vis_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    # Then generate visemes
    gallery = generate_visemes(
        style="test char", name="vis_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    head_dir = tmp_heads_dir / "vis_test"
    svg_files = list(head_dir.glob("*.svg"))
    assert len(svg_files) == 15  # sil + 14 others
    assert gallery.name == "gallery.html"


def test_generate_visemes_no_base_raises(tmp_heads_dir, mock_llm_client):
    with pytest.raises(FileNotFoundError):
        generate_visemes(
            style="test char", name="no_base",
            out_root=tmp_heads_dir, client=mock_llm_client,
        )


def test_generate_visemes_skip_existing(tmp_heads_dir, mock_llm_client):
    # Create full set
    generate(
        style="test char", name="skip_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    call_count_before = mock_llm_client.generate.call_count

    # Run again with skip_existing
    generate_visemes(
        style="test char", name="skip_test",
        out_root=tmp_heads_dir, skip_existing=True, client=mock_llm_client,
    )
    # Should not have made additional LLM calls
    assert mock_llm_client.generate.call_count == call_count_before


def test_generate_full(tmp_heads_dir, mock_llm_client):
    gallery = generate(
        style="test char", name="full_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    head_dir = tmp_heads_dir / "full_test"
    svg_files = list(head_dir.glob("*.svg"))
    assert len(svg_files) == 15
    assert gallery.exists()


def test_generate_with_preset(tmp_heads_dir, mock_llm_client):
    from voxhelm.core.presets import PRESETS
    style = PRESETS["young_woman"]
    gallery = generate(
        style=style, name="preset_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    assert (tmp_heads_dir / "preset_test" / "sil.svg").exists()


def test_load_svgs(tmp_heads_dir, mock_llm_client):
    generate(
        style="test char", name="load_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
    )
    svgs = load_svgs(tmp_heads_dir / "load_test")
    assert len(svgs) == 15
    assert "sil" in svgs
    assert svgs["sil"].startswith("<svg")


def test_clean_svg_strips_fences():
    fenced = "```svg\n<svg>test</svg>\n```"
    assert _clean_svg(fenced) == "<svg>test</svg>"


def test_clean_svg_passthrough():
    raw = "<svg>test</svg>"
    assert _clean_svg(raw) == raw


def test_build_prompt_base():
    prompt = build_prompt("young woman", "sil", None)
    assert "sil" in prompt
    assert "reference frame" in prompt.lower()


def test_build_prompt_viseme_has_reference():
    prompt = build_prompt("young woman", "PP", "<svg>ref</svg>")
    assert "Reference SVG" in prompt
    assert "<svg>ref</svg>" in prompt


def test_progress_callback(tmp_heads_dir, mock_llm_client):
    calls = []
    generate_base(
        style="test char", name="progress_test",
        out_root=tmp_heads_dir, client=mock_llm_client,
        on_progress=lambda v, i, t, s: calls.append((v, s)),
    )
    assert len(calls) >= 1
    assert calls[0][0] == "sil"
