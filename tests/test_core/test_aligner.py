"""Tests for voxhelm.core.aligner (wav2vec2 forced alignment)."""

import pytest
from voxhelm.core.aligner import is_available, pcm_to_waveform


def test_is_available():
    """wav2vec2 alignment should be available if torch is installed."""
    # In our test env torch is installed
    assert is_available() is True


def test_pcm_to_waveform():
    """Convert raw PCM16 to torch tensor."""
    import array
    # Generate 1 second of silence at 16kHz (16000 samples, 16-bit)
    silence = array.array("h", [0] * 16000)
    pcm_bytes = silence.tobytes()

    waveform = pcm_to_waveform(pcm_bytes, sample_rate=16000)
    assert waveform.shape == (1, 16000)
    assert waveform.max().item() == 0.0


def test_pcm_to_waveform_sine():
    """Convert a sine wave PCM to tensor and check range."""
    import array
    import math
    # Generate 0.1s of 440Hz sine at 16kHz
    sr = 16000
    samples = [int(32767 * math.sin(2 * math.pi * 440 * i / sr)) for i in range(1600)]
    pcm_bytes = array.array("h", samples).tobytes()

    waveform = pcm_to_waveform(pcm_bytes, sample_rate=sr)
    assert waveform.shape == (1, 1600)
    assert waveform.max().item() <= 1.0
    assert waveform.min().item() >= -1.0


def test_aligned_timeline():
    """aligned_to_timeline produces visemes from aligned word data."""
    from voxhelm.core.timeline import aligned_to_timeline

    aligned_words = [
        {"word": "hello", "start": 0.0, "end": 0.4, "chars": [
            {"char": "h", "start": 0.0, "end": 0.08},
            {"char": "e", "start": 0.08, "end": 0.16},
            {"char": "l", "start": 0.16, "end": 0.24},
            {"char": "l", "start": 0.24, "end": 0.32},
            {"char": "o", "start": 0.32, "end": 0.4},
        ]},
        {"word": "world", "start": 0.5, "end": 0.9, "chars": [
            {"char": "w", "start": 0.5, "end": 0.58},
            {"char": "o", "start": 0.58, "end": 0.66},
            {"char": "r", "start": 0.66, "end": 0.74},
            {"char": "l", "start": 0.74, "end": 0.82},
            {"char": "d", "start": 0.82, "end": 0.9},
        ]},
    ]

    timeline = aligned_to_timeline(aligned_words)
    assert len(timeline) >= 3
    assert timeline[0]["v"] == "sil"
    # Should have non-sil visemes
    non_sil = [e for e in timeline if e["v"] != "sil"]
    assert len(non_sil) >= 2
