"""Tests for voxhelm.core.visemes."""

from voxhelm.core.visemes import (
    VISEMES, ALL_VISEMES, PHONEME_TO_VISEME, CMU, ph_to_vis,
)


def test_all_visemes_count():
    assert len(ALL_VISEMES) == 15


def test_all_visemes_matches_dict():
    assert list(VISEMES.keys()) == ALL_VISEMES


def test_viseme_has_phonemes_and_mouth():
    for v, info in VISEMES.items():
        assert "phonemes" in info, f"{v} missing phonemes"
        assert "mouth" in info, f"{v} missing mouth"


def test_phoneme_to_viseme_known():
    assert PHONEME_TO_VISEME["P"] == "PP"
    assert PHONEME_TO_VISEME["F"] == "FF"
    assert PHONEME_TO_VISEME["AA"] == "aa"
    assert PHONEME_TO_VISEME["S"] == "SS"
    assert PHONEME_TO_VISEME["UW"] == "U"


def test_ph_to_vis_strips_stress():
    assert ph_to_vis("AA1") == "aa"
    assert ph_to_vis("IY0") == "I"
    assert ph_to_vis("OW1") == "O"


def test_ph_to_vis_unknown_returns_sil():
    assert ph_to_vis("XX") == "sil"
    assert ph_to_vis("") == "sil"


def test_cmu_dict_has_common_words():
    assert "hello" in CMU
    assert "the" in CMU
    assert "world" in CMU


def test_cmu_entries_are_phoneme_lists():
    for word, phonemes in CMU.items():
        assert isinstance(phonemes, list), f"{word}: expected list"
        assert len(phonemes) > 0, f"{word}: empty phoneme list"
