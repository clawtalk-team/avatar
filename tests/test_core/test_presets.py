"""Tests for voxhelm.core.presets."""

from voxhelm.core.presets import PRESETS, get_preset, list_presets
import pytest


def test_preset_count():
    assert len(PRESETS) == 14


def test_list_presets_returns_dict():
    result = list_presets()
    assert isinstance(result, dict)
    assert len(result) == 14


def test_get_preset_known():
    desc = get_preset("young_woman")
    assert isinstance(desc, str)
    assert "woman" in desc.lower()


def test_get_preset_unknown():
    with pytest.raises(KeyError):
        get_preset("nonexistent_preset")


def test_all_presets_are_strings():
    for key, desc in PRESETS.items():
        assert isinstance(key, str)
        assert isinstance(desc, str)
        assert len(desc) > 10
