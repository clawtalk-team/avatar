"""Viseme timeline generation from word timestamps and phoneme lookup."""

from __future__ import annotations

import re

from .visemes import CMU, ph_to_vis


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
            timeline.append({"t": round(start, 4), "v": "aa", "ph": "?"})
            timeline.append({"t": round(end, 4), "v": "sil", "ph": "SIL"})
            continue

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
