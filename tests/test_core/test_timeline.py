"""Tests for voxhelm.core.timeline."""

from voxhelm.core.timeline import words_to_timeline


def test_empty_words():
    result = words_to_timeline([])
    assert len(result) == 1
    assert result[0]["v"] == "sil"
    assert result[0]["t"] == 0.0


def test_single_known_word():
    words = [{"word": "hello", "start": 0.1, "end": 0.5}]
    result = words_to_timeline(words)
    # Should have: initial sil, phonemes for "hello", trailing sil
    assert result[0]["v"] == "sil"
    assert result[-1]["v"] == "sil"
    assert len(result) >= 3


def test_unknown_word_fallback():
    words = [{"word": "xyzzy", "start": 0.1, "end": 0.5}]
    result = words_to_timeline(words)
    # Unknown word falls back to 'aa'
    visemes = [e["v"] for e in result]
    assert "aa" in visemes


def test_timeline_ordering():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    result = words_to_timeline(words)
    times = [e["t"] for e in result]
    assert times == sorted(times), "Timeline not monotonically increasing"


def test_deduplication():
    # Two words that produce the same viseme sequence should get deduplicated
    words = [
        {"word": "the", "start": 0.0, "end": 0.2},
        {"word": "the", "start": 0.3, "end": 0.5},
    ]
    result = words_to_timeline(words)
    # Should not have consecutive identical visemes (within 20ms threshold)
    for i in range(1, len(result)):
        if result[i]["v"] == result[i - 1]["v"]:
            assert result[i]["t"] > result[i - 1]["t"] + 0.02


def test_multiple_words():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    result = words_to_timeline(words)
    assert len(result) >= 4  # At least: sil, some phonemes, sil
