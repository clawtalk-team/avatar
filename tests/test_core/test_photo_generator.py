"""Tests for voxhelm.core.photo_generator (photo generation with mocked API)."""

import json
import pytest
from pathlib import Path

from voxhelm.core.visemes import ALL_VISEMES


def test_generate_base_creates_files(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_base
    result = generate_base(
        style="test character", name="photo_base",
        out_root=tmp_heads_dir,
    )
    head_dir = tmp_heads_dir / "photo_base"
    assert result.exists()
    assert result.name == "base.png"
    assert (head_dir / "sil.png").exists()
    assert (head_dir / "base.png").exists()


def test_generate_base_creates_manifest(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_base
    generate_base(style="test", name="manifest_test", out_root=tmp_heads_dir)

    manifest = json.loads((tmp_heads_dir / "manifest_test" / "manifest.json").read_text())
    assert manifest["base"] == "base.png"
    assert "sil" in manifest["visemes"]


def test_generate_visemes_creates_pngs(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_base, generate_visemes
    generate_base(style="test", name="vis_photo", out_root=tmp_heads_dir)
    gallery = generate_visemes(style="test", name="vis_photo", out_root=tmp_heads_dir)

    head_dir = tmp_heads_dir / "vis_photo"
    png_files = [f for f in head_dir.glob("*.png") if f.name != "base.png" and f.name != "blink.png"]
    assert len(png_files) == 15
    assert gallery.name == "gallery.html"


def test_generate_visemes_includes_blink(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_base, generate_visemes
    generate_base(style="test", name="blink_test", out_root=tmp_heads_dir)
    generate_visemes(style="test", name="blink_test", out_root=tmp_heads_dir, include_blink=True)
    assert (tmp_heads_dir / "blink_test" / "blink.png").exists()


def test_generate_visemes_no_blink(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_base, generate_visemes
    generate_base(style="test", name="noblink_test", out_root=tmp_heads_dir)
    generate_visemes(style="test", name="noblink_test", out_root=tmp_heads_dir, include_blink=False)
    assert not (tmp_heads_dir / "noblink_test" / "blink.png").exists()


def test_generate_visemes_no_base_raises(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate_visemes
    with pytest.raises(FileNotFoundError):
        generate_visemes(style="test", name="no_base", out_root=tmp_heads_dir)


def test_generate_full(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate
    gallery = generate(style="test", name="full_photo", out_root=tmp_heads_dir)
    head_dir = tmp_heads_dir / "full_photo"
    png_files = [f for f in head_dir.glob("*.png") if f.name != "base.png" and f.name != "blink.png"]
    assert len(png_files) == 15
    assert gallery.exists()


def test_generate_skip_existing(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate
    generate(style="test", name="skip_photo", out_root=tmp_heads_dir)

    # Second run with skip_existing should not fail
    gallery = generate(style="test", name="skip_photo", out_root=tmp_heads_dir, skip_existing=True)
    assert gallery.exists()


def test_load_pngs(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate, load_pngs
    generate(style="test", name="load_photo", out_root=tmp_heads_dir)
    pngs = load_pngs(tmp_heads_dir / "load_photo")
    assert len(pngs) == 15
    assert "sil" in pngs
    assert isinstance(pngs["sil"], bytes)


def test_gallery_html_created(tmp_heads_dir, mock_photo_generate, mock_openrouter_key):
    from voxhelm.core.photo_generator import generate
    generate(style="test character", name="gallery_photo", out_root=tmp_heads_dir)
    gallery = tmp_heads_dir / "gallery_photo" / "gallery.html"
    assert gallery.exists()
    html = gallery.read_text()
    assert "gallery_photo" in html
    assert "photo" in html.lower()
