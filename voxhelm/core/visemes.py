"""Viseme definitions, phoneme-to-viseme mapping, and CMU dictionary subset."""

import re

# ── 15 OVR viseme definitions ────────────────────────────────────────────────

VISEMES: dict[str, dict[str, str]] = {
    "sil": {"phonemes": "silence",        "mouth": "closed, lips neutral, relaxed"},
    "PP":  {"phonemes": "p, b, m",        "mouth": "lips firmly pressed together, slight tension"},
    "FF":  {"phonemes": "f, v",           "mouth": "upper teeth lightly resting on lower lip, slight gap"},
    "TH":  {"phonemes": "th, dh",         "mouth": "tongue tip just visible between slightly parted teeth"},
    "DD":  {"phonemes": "t, d",           "mouth": "mouth slightly open, tongue behind upper teeth"},
    "kk":  {"phonemes": "k, g",           "mouth": "mouth open, back of tongue raised, mid-open"},
    "CH":  {"phonemes": "ch, j, sh, zh",  "mouth": "lips rounded and slightly forward, slightly open"},
    "SS":  {"phonemes": "s, z",           "mouth": "lips wide and slightly parted, teeth nearly closed"},
    "nn":  {"phonemes": "n, l, ng",       "mouth": "mouth slightly open, relaxed tongue position"},
    "RR":  {"phonemes": "r",              "mouth": "lips slightly rounded and forward, mouth slightly open"},
    "aa":  {"phonemes": "ah, aa, ae",     "mouth": "wide open, jaw dropped, lips relaxed and wide"},
    "E":   {"phonemes": "eh, ey",         "mouth": "mouth open half-way, lips wide and spread"},
    "I":   {"phonemes": "ih, iy",         "mouth": "mouth barely open, lips wide and tightly spread"},
    "O":   {"phonemes": "oh, ao, ow",     "mouth": "lips rounded into an O shape, mouth open"},
    "U":   {"phonemes": "oo, uw, uh",     "mouth": "lips tightly rounded and forward like a kiss, small opening"},
}

ALL_VISEMES: list[str] = list(VISEMES.keys())

# ── ARPAbet → OVR viseme mapping ─────────────────────────────────────────────

PHONEME_TO_VISEME: dict[str, str] = {
    "SIL": "sil", "SP": "sil", "": "sil",
    "P": "PP", "B": "PP", "M": "PP",
    "F": "FF", "V": "FF",
    "TH": "TH", "DH": "TH",
    "T": "DD", "D": "DD",
    "K": "kk", "G": "kk",
    "CH": "CH", "JH": "CH", "SH": "CH", "ZH": "CH",
    "S": "SS", "Z": "SS",
    "N": "nn", "L": "nn", "NG": "nn",
    "R": "RR", "ER": "RR",
    "AA": "aa", "AH": "aa", "AE": "aa",
    "EH": "E", "EY": "E",
    "IH": "I", "IY": "I",
    "AO": "O", "OW": "O",
    "UW": "U", "UH": "U",
    "OY": "O", "AW": "aa", "AY": "aa",
    "HH": "sil", "W": "U", "Y": "I",
}

# ── CMU pronouncing dictionary ────────────────────────────────────────────────

_cmu_cache: dict[str, list[str]] | None = None


def _load_cmudict() -> dict[str, list[str]]:
    """Load the full CMU pronouncing dictionary via nltk (~134K words).

    Falls back to a small built-in subset if nltk is not installed.
    """
    global _cmu_cache
    if _cmu_cache is not None:
        return _cmu_cache

    try:
        import nltk
        nltk.download("cmudict", quiet=True)
        from nltk.corpus import cmudict
        _cmu_cache = cmudict.dict()
        return _cmu_cache
    except (ImportError, LookupError):
        pass

    # Fallback: small built-in subset for environments without nltk
    _cmu_cache = {
        "the": [["DH", "AH0"]], "a": [["AH0"]], "hello": [["HH", "AH0", "L", "OW1"]],
        "world": [["W", "ER1", "L", "D"]], "and": [["AE1", "N", "D"]],
        "to": [["T", "UW1"]], "is": [["IH1", "Z"]], "it": [["IH1", "T"]],
        "you": [["Y", "UW1"]], "this": [["DH", "IH1", "S"]],
        "that": [["DH", "AE1", "T"]], "of": [["AH0", "V"]],
        "in": [["IH0", "N"]], "for": [["F", "AO1", "R"]],
        "not": [["N", "AA1", "T"]], "on": [["AO1", "N"]],
    }
    return _cmu_cache


def cmu_lookup(word: str) -> list[str] | None:
    """Look up a word's phonemes in the CMU dictionary.

    Returns the first pronunciation variant, or None if not found.
    """
    d = _load_cmudict()
    clean = re.sub(r"[^a-z']", "", word.lower())
    entries = d.get(clean)
    if not entries:
        return None
    return entries[0]


# ── Letter-to-phoneme heuristic for unknown words ───────────────────────────

# Common English digraphs and their ARPAbet equivalents
_DIGRAPHS: list[tuple[str, list[str]]] = [
    ("th", ["TH"]),
    ("sh", ["SH"]),
    ("ch", ["CH"]),
    ("ph", ["F"]),
    ("wh", ["W"]),
    ("ck", ["K"]),
    ("ng", ["NG"]),
    ("qu", ["K", "W"]),
    ("oo", ["UW"]),
    ("ee", ["IY"]),
    ("ea", ["IY"]),
    ("ou", ["AW"]),
    ("ow", ["OW"]),
    ("ai", ["EY"]),
    ("ay", ["EY"]),
    ("oi", ["OY"]),
    ("oy", ["OY"]),
    ("au", ["AO"]),
    ("aw", ["AO"]),
    ("igh", ["AY"]),
]

# Single letter fallbacks
_LETTER_PHONEME: dict[str, str] = {
    "a": "AE", "b": "B", "c": "K", "d": "D", "e": "EH",
    "f": "F", "g": "G", "h": "HH", "i": "IH", "j": "JH",
    "k": "K", "l": "L", "m": "M", "n": "N", "o": "AA",
    "p": "P", "q": "K", "r": "R", "s": "S", "t": "T",
    "u": "AH", "v": "V", "w": "W", "x": "K", "y": "IY",
    "z": "Z",
}

# Common suffixes → phoneme sequences (strip before processing, append after)
_SUFFIXES: list[tuple[str, list[str]]] = [
    ("tion", ["SH", "AH", "N"]),
    ("sion", ["ZH", "AH", "N"]),
    ("ness", ["N", "AH", "S"]),
    ("ment", ["M", "AH", "N", "T"]),
    ("able", ["AH", "B", "AH", "L"]),
    ("ible", ["AH", "B", "AH", "L"]),
    ("ful", ["F", "AH", "L"]),
    ("less", ["L", "AH", "S"]),
    ("ing", ["IH", "NG"]),
    ("ous", ["AH", "S"]),
    ("ive", ["IH", "V"]),
    ("ly", ["L", "IY"]),
    ("ed", ["D"]),
    ("er", ["ER"]),
    ("es", ["Z"]),
    ("'s", ["Z"]),
]


def guess_phonemes(word: str) -> list[str]:
    """Guess ARPAbet phonemes from English spelling for unknown words.

    Uses digraph matching, suffix stripping, and single-letter fallback.
    Not perfect, but much better than mapping everything to 'aa'.
    """
    clean = re.sub(r"[^a-z']", "", word.lower())
    if not clean:
        return ["AH"]

    # Check for common suffixes
    suffix_phonemes: list[str] = []
    for suffix, phonemes in _SUFFIXES:
        if clean.endswith(suffix) and len(clean) > len(suffix) + 1:
            clean = clean[: -len(suffix)]
            suffix_phonemes = list(phonemes)
            break

    # Scan left to right, trying digraphs first then single letters
    result: list[str] = []
    i = 0
    while i < len(clean):
        matched = False
        # Try trigraphs and digraphs (longest first)
        for digraph, phonemes in _DIGRAPHS:
            if clean[i:].startswith(digraph):
                result.extend(phonemes)
                i += len(digraph)
                matched = True
                break
        if not matched:
            ch = clean[i]
            # Skip silent e at end
            if ch == "e" and i == len(clean) - 1 and len(clean) > 2:
                i += 1
                continue
            result.append(_LETTER_PHONEME.get(ch, "AH"))
            i += 1

    result.extend(suffix_phonemes)
    return result if result else ["AH"]


class _CMUProxy:
    """Dict-like proxy that loads the full CMU dict on first access."""
    def get(self, word, default=None):
        return cmu_lookup(word) or default
    def __contains__(self, word):
        return cmu_lookup(word) is not None
    def __getitem__(self, word):
        result = cmu_lookup(word)
        if result is None:
            raise KeyError(word)
        return result

CMU = _CMUProxy()


def ph_to_vis(ph: str) -> str:
    """Convert an ARPAbet phoneme (with optional stress digit) to an OVR viseme."""
    base = re.sub(r"\d", "", ph)
    return PHONEME_TO_VISEME.get(ph, PHONEME_TO_VISEME.get(base, "sil"))
