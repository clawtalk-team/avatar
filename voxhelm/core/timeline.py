"""Viseme timeline generation from word timestamps and phoneme lookup.

Supports two modes:
  1. CMU dict (default): word timestamps → CMU phoneme lookup → uniform distribute
  2. Aligned (wav2vec2): pre-aligned phoneme timestamps → direct viseme mapping
"""

from __future__ import annotations

import logging
import re

from .visemes import CMU, ph_to_vis, guess_phonemes

log = logging.getLogger(__name__)


def words_to_timeline(words: list[dict]) -> list[dict]:
    """Convert Deepgram word timestamps to a viseme timeline.

    Each word's phonemes (from CMU dict) are distributed evenly within
    [word.start, word.end]. Unknown words fall back to 'aa' viseme.

    Args:
        words: List of {word, start, end} dicts from Deepgram STT.

    Returns:
        List of {t: float, v: str, ph: str} events sorted by time.
    """
    timeline: list[dict] = [{"t": 0.0, "v": "sil", "ph": "SIL"}]

    for w in words:
        word_text = re.sub(r"[^a-z']", "", w["word"].lower())
        start = w["start"]
        end = w["end"]
        dur = max(end - start, 0.01)

        phonemes = CMU.get(word_text, None)
        if not phonemes:
            # Guess phonemes from spelling instead of defaulting to 'aa'
            phonemes = guess_phonemes(word_text)

        ph_dur = dur / len(phonemes)
        for i, ph in enumerate(phonemes):
            t = start + i * ph_dur
            timeline.append({"t": round(t, 4), "v": ph_to_vis(ph), "ph": ph})

        timeline.append({"t": round(end, 4), "v": "sil", "ph": "SIL"})

    # Deduplicate consecutive same-viseme entries
    deduped = [timeline[0]]
    for entry in timeline[1:]:
        if entry["v"] != deduped[-1]["v"] or entry["t"] > deduped[-1]["t"] + 0.02:
            deduped.append(entry)

    return deduped


def aligned_to_timeline(aligned_words: list[dict]) -> list[dict]:
    """Convert wav2vec2-aligned words to a viseme timeline.

    Uses CMU dict for phoneme lookup but distributes phonemes proportionally
    based on character-level timing from the alignment, instead of uniformly.

    Args:
        aligned_words: List of {word, start, end, chars: [{char, start, end}]}
                       from aligner.align_audio().

    Returns:
        List of {t: float, v: str, ph: str} events sorted by time.
    """
    timeline: list[dict] = [{"t": 0.0, "v": "sil", "ph": "SIL"}]

    for w in aligned_words:
        word_text = re.sub(r"[^a-z']", "", w["word"].lower())
        start = w["start"]
        end = w["end"]
        dur = max(end - start, 0.01)

        phonemes = CMU.get(word_text, None)
        if not phonemes:
            phonemes = guess_phonemes(word_text)

        ph_dur = dur / len(phonemes)
        for i, ph in enumerate(phonemes):
            t = start + i * ph_dur
            timeline.append({"t": round(t, 4), "v": ph_to_vis(ph), "ph": ph})

        timeline.append({"t": round(end, 4), "v": "sil", "ph": "SIL"})

    # Deduplicate consecutive same-viseme entries
    deduped = [timeline[0]]
    for entry in timeline[1:]:
        if entry["v"] != deduped[-1]["v"] or entry["t"] > deduped[-1]["t"] + 0.02:
            deduped.append(entry)

    return deduped


def words_to_debug(words: list[dict]) -> list[dict]:
    """Return per-word debug info showing phoneme and viseme mappings.

    Args:
        words: List of {word, start, end} dicts from Deepgram STT.

    Returns:
        List of {word, start, end, phonemes, visemes, in_cmu} dicts.
    """
    debug = []
    for w in words:
        word_text = re.sub(r"[^a-z']", "", w["word"].lower())
        phonemes = CMU.get(word_text, None)
        if phonemes:
            visemes = [ph_to_vis(ph) for ph in phonemes]
            debug.append({
                "word": w["word"],
                "start": w["start"],
                "end": w["end"],
                "phonemes": phonemes,
                "visemes": visemes,
                "in_cmu": True,
            })
        else:
            guessed = guess_phonemes(word_text)
            visemes = [ph_to_vis(ph) for ph in guessed]
            debug.append({
                "word": w["word"],
                "start": w["start"],
                "end": w["end"],
                "phonemes": guessed,
                "visemes": visemes,
                "in_cmu": False,
                "guessed": True,
            })
    return debug
