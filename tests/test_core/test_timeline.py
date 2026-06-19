"""Tests for voxhelm.core.timeline."""

from voxhelm.core.timeline import words_to_timeline, words_to_debug


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


def test_unknown_word_guessed():
    words = [{"word": "xyzzy", "start": 0.1, "end": 0.5}]
    result = words_to_timeline(words)
    # Unknown word gets guessed phonemes from spelling (not just 'aa')
    non_sil = [e for e in result if e["v"] != "sil"]
    assert len(non_sil) >= 1, "Should have at least one guessed viseme"


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


# ── Debug breakdown tests ──────────────────────────────────────────────────

def test_debug_known_words():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    debug = words_to_debug(words)
    assert len(debug) == 2
    assert debug[0]["word"] == "hello"
    assert debug[0]["in_cmu"] is True
    assert len(debug[0]["phonemes"]) > 0
    assert len(debug[0]["visemes"]) > 0


def test_debug_unknown_word():
    words = [{"word": "xyzzyplugh", "start": 0.0, "end": 0.5}]
    debug = words_to_debug(words)
    assert len(debug) == 1
    assert debug[0]["in_cmu"] is False
    assert debug[0].get("guessed") is True
    # Should have guessed phonemes from spelling, not empty
    assert len(debug[0]["phonemes"]) >= 1
    assert len(debug[0]["visemes"]) >= 1


def test_debug_viseme_variety():
    """Sentence with known words should produce multiple distinct visemes."""
    words = [
        {"word": "shall", "start": 0.0, "end": 0.3},
        {"word": "we", "start": 0.35, "end": 0.5},
        {"word": "find", "start": 0.55, "end": 0.8},
        {"word": "beach", "start": 0.85, "end": 1.1},
        {"word": "zoo", "start": 1.15, "end": 1.4},
    ]
    debug = words_to_debug(words)
    all_visemes = set()
    for w in debug:
        all_visemes.update(w["visemes"])
    # These words should produce at least 8 distinct visemes
    assert len(all_visemes) >= 8, f"Only {len(all_visemes)} visemes: {all_visemes}"
    assert all(w["in_cmu"] for w in debug), "All test words should be in CMU"


def test_debug_matches_timeline():
    """Debug visemes should be a subset of timeline visemes (plus sil)."""
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    debug = words_to_debug(words)
    timeline = words_to_timeline(words)

    # Non-sil visemes from debug should all appear in the timeline
    debug_visemes = set()
    for w in debug:
        debug_visemes.update(v for v in w["visemes"] if v != "sil")
    timeline_visemes = set(e["v"] for e in timeline if e["v"] != "sil")
    assert debug_visemes.issubset(timeline_visemes), \
        f"Debug has {debug_visemes - timeline_visemes} not in timeline"
