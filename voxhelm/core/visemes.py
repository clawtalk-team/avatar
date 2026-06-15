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

# ── CMU pronouncing dictionary subset ─────────────────────────────────────────

CMU: dict[str, list[str]] = {
    "the": ["DH", "AH0"], "quick": ["K", "W", "IH1", "K"],
    "brown": ["B", "R", "AW1", "N"], "fox": ["F", "AA1", "K", "S"],
    "jumps": ["JH", "AH1", "M", "P", "S"], "over": ["OW1", "V", "ER0"],
    "five": ["F", "AY1", "V"], "lazy": ["L", "EY1", "Z", "IY0"],
    "dogs": ["D", "AO1", "G", "Z"], "but": ["B", "AH1", "T"],
    "they": ["DH", "EY1"], "should": ["SH", "UH1", "D"],
    "also": ["AO1", "L", "S", "OW0"], "be": ["B", "IY1"],
    "very": ["V", "EH1", "R", "IY0"], "happy": ["HH", "AE1", "P", "IY0"],
    "talking": ["T", "AO1", "K", "IH0", "NG"], "with": ["W", "IH1", "DH"],
    "people": ["P", "IY1", "P", "AH0", "L"], "hello": ["HH", "AH0", "L", "OW1"],
    "world": ["W", "ER1", "L", "D"], "how": ["HH", "AW1"], "are": ["AA1", "R"],
    "you": ["Y", "UW1"], "today": ["T", "AH0", "D", "EY1"], "i": ["AY1"],
    "am": ["AE1", "M"], "doing": ["D", "UW1", "IH0", "NG"],
    "well": ["W", "EH1", "L"], "thank": ["TH", "AE1", "NG", "K"],
    "thanks": ["TH", "AE1", "NG", "K", "S"], "and": ["AE1", "N", "D"],
    "of": ["AH0", "V"], "to": ["T", "UW1"], "a": ["AH0"],
    "is": ["IH1", "Z"], "in": ["IH0", "N"], "it": ["IH1", "T"],
    "that": ["DH", "AE1", "T"], "this": ["DH", "IH1", "S"],
    "my": ["M", "AY1"], "your": ["Y", "AO1", "R"], "all": ["AO1", "L"],
    "have": ["HH", "AE1", "V"], "for": ["F", "AO1", "R"],
    "on": ["AO1", "N"], "can": ["K", "AE1", "N"], "not": ["N", "AA1", "T"],
    "will": ["W", "IH1", "L"], "what": ["W", "AH1", "T"], "so": ["S", "OW1"],
    "know": ["N", "OW1"], "go": ["G", "OW1"], "love": ["L", "AH1", "V"],
    "some": ["S", "AH1", "M"], "time": ["T", "AY1", "M"],
    "good": ["G", "UH1", "D"], "now": ["N", "AW1"],
    "think": ["TH", "IH1", "NG", "K"], "just": ["JH", "AH1", "S", "T"],
    "one": ["W", "AH1", "N"], "up": ["AH1", "P"], "out": ["AW1", "T"],
    "no": ["N", "OW1"], "at": ["AE1", "T"], "an": ["AE1", "N"],
    "do": ["D", "UW1"], "call": ["K", "AO1", "L"],
    "choose": ["CH", "UW1", "Z"], "sharing": ["SH", "EH1", "R", "IH0", "NG"],
    "books": ["B", "UH1", "K", "S"], "red": ["R", "EH1", "D"],
    "big": ["B", "IH1", "G"], "eight": ["EY1", "T"],
    "every": ["EH1", "V", "R", "IY0"], "say": ["S", "EY1"],
    "says": ["S", "EH1", "Z"], "through": ["TH", "R", "UW1"],
    "three": ["TH", "R", "IY1"], "many": ["M", "EH1", "N", "IY0"],
    "new": ["N", "UW1"], "way": ["W", "EY1"], "see": ["S", "IY1"],
    "make": ["M", "EY1", "K"], "come": ["K", "AH1", "M"],
    "look": ["L", "UH1", "K"], "more": ["M", "AO1", "R"],
    "get": ["G", "EH1", "T"], "like": ["L", "AY1", "K"],
    "him": ["HH", "IH1", "M"], "his": ["HH", "IH1", "Z"],
    "from": ["F", "R", "AH1", "M"], "then": ["DH", "EH1", "N"],
    "there": ["DH", "EH1", "R"], "these": ["DH", "IY1", "Z"],
    "those": ["DH", "OW1", "Z"], "use": ["Y", "UW1", "Z"],
    "each": ["IY1", "CH"], "which": ["W", "IH1", "CH"],
    "their": ["DH", "EH1", "R"], "talk": ["T", "AO1", "K"],
    "speech": ["S", "P", "IY1", "CH"], "voice": ["V", "OY1", "S"],
    "face": ["F", "EY1", "S"], "mouth": ["M", "AW1", "TH"],
    "lip": ["L", "IH1", "P"], "lips": ["L", "IH1", "P", "S"],
    "show": ["SH", "OW1"], "shape": ["SH", "EY1", "P"],
    "different": ["D", "IH1", "F", "R", "AH0", "N", "T"],
    "when": ["W", "EH1", "N"], "phoneme": ["F", "OW1", "N", "IY0", "M"],
    "changes": ["CH", "EY1", "N", "JH", "AH0", "Z"],
    "watch": ["W", "AO1", "CH"],
    "carefully": ["K", "EH1", "R", "F", "AH0", "L", "IY0"],
    "as": ["AE1", "Z"], "moves": ["M", "UW1", "V", "Z"],
    "between": ["B", "IH0", "T", "W", "IY1", "N"],
    "position": ["P", "AH0", "Z", "IH1", "SH", "AH0", "N"],
    "positions": ["P", "AH0", "Z", "IH1", "SH", "AH0", "N", "Z"],
    "notice": ["N", "OW1", "T", "IH0", "S"],
    "open": ["OW1", "P", "AH0", "N"], "close": ["K", "L", "OW1", "Z"],
    "round": ["R", "AW1", "N", "D"], "spread": ["S", "P", "R", "EH1", "D"],
    "jaw": ["JH", "AO1"], "drops": ["D", "R", "AA1", "P", "S"],
    "wider": ["W", "AY1", "D", "ER0"],
}


def ph_to_vis(ph: str) -> str:
    """Convert an ARPAbet phoneme (with optional stress digit) to an OVR viseme."""
    base = re.sub(r"\d", "", ph)
    return PHONEME_TO_VISEME.get(ph, PHONEME_TO_VISEME.get(base, "sil"))
