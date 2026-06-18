"""Tests for voxhelm.core.visemes."""

from voxhelm.core.visemes import (
    VISEMES, ALL_VISEMES, PHONEME_TO_VISEME, CMU, ph_to_vis, guess_phonemes,
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


def test_cmu_lookup_returns_phoneme_list():
    from voxhelm.core.visemes import cmu_lookup
    for word in ["hello", "world", "the", "shall", "beach", "quiet"]:
        phonemes = cmu_lookup(word)
        assert phonemes is not None, f"{word}: not in CMU dict"
        assert isinstance(phonemes, list), f"{word}: expected list"
        assert len(phonemes) > 0, f"{word}: empty phoneme list"


def test_cmu_lookup_unknown_returns_none():
    from voxhelm.core.visemes import cmu_lookup
    assert cmu_lookup("xyzzyplugh") is None


# ── Guess phonemes (G2P fallback) ─────────────────────────────────────────

def test_guess_phonemes_returns_list():
    result = guess_phonemes("blockchain")
    assert isinstance(result, list)
    assert len(result) >= 3


def test_guess_phonemes_consonants():
    result = guess_phonemes("stop")
    visemes = [ph_to_vis(p) for p in result]
    assert "SS" in visemes  # s → S → SS
    assert "DD" in visemes  # t → T → DD
    assert "PP" in visemes  # p → P → PP


def test_guess_phonemes_digraphs():
    result = guess_phonemes("church")
    visemes = [ph_to_vis(p) for p in result]
    assert "CH" in visemes  # ch → CH


def test_guess_phonemes_suffix_ing():
    result = guess_phonemes("running")
    # Should have NG from -ing suffix
    assert "NG" in result or "IH" in result


def test_guess_phonemes_suffix_tion():
    result = guess_phonemes("nation")
    visemes = [ph_to_vis(p) for p in result]
    # -tion → SH AH N
    assert "CH" in visemes  # SH → CH viseme


def test_guess_phonemes_diverse_visemes():
    """An unknown word should produce multiple distinct visemes, not just 'aa'."""
    result = guess_phonemes("smartphone")
    visemes = set(ph_to_vis(p) for p in result)
    visemes.discard("sil")
    assert len(visemes) >= 3, f"Only {len(visemes)} visemes from 'smartphone': {sorted(visemes)}"


def test_guess_phonemes_empty_word():
    result = guess_phonemes("")
    assert result == ["AH"]


def test_guess_phonemes_silent_e():
    result = guess_phonemes("make")
    # Should skip silent e, not produce extra phoneme
    assert len(result) <= 4
