#!/usr/bin/env python3
"""
lipsync_pipeline.py  —  Deepgram TTS → Whisper word-timestamps → viseme timeline

Outputs:
  outputs/lipsync/audio.mp3          Raw TTS audio
  outputs/lipsync/lipsync_data.js    JS file consumed by demo.html
                                      (sets window.LIPSYNC_DATA)
"""

import json
import os
import re
import sys
import requests
import nltk
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
# Viseme-rich default: bilabials (PP), fricatives (FF), sibilants (SS/CH),
# rounded vowels (O/U), wide vowels (aa/E), rhotics (RR) — exercises most transitions.
SENTENCE = ("Hello there, and welcome aboard. "
            "Would you like a warm cup of coffee before we show you the ship? "
            "She found five shiny seashells by the shore. "
            "Now breathe slowly, relax, and enjoy this amazing journey.")

OUT_DIR   = Path(__file__).parent.parent / "outputs" / "lipsync"
AUDIO_PATH = OUT_DIR / "audio.mp3"
DATA_PATH  = OUT_DIR / "lipsync_data.js"

# ── ARPAbet → OVR LipSync viseme map ────────────────────────────────────────
PHONEME_TO_VISEME = {
    # Bilabials
    "P": "PP", "B": "PP", "M": "PP",
    # Labiodentals
    "F": "FF", "V": "FF",
    # Dentals
    "TH": "TH", "DH": "TH",
    # Alveolars (stops)
    "T": "DD", "D": "DD",
    # Velars
    "K": "kk", "G": "kk",
    # Affricates / postalveolars
    "CH": "CH", "JH": "CH", "SH": "CH", "ZH": "CH",
    # Sibilants
    "S": "SS", "Z": "SS",
    # Nasals + lateral
    "N": "nn", "L": "nn", "NG": "nn",
    # Rhotic
    "R": "RR", "ER": "RR",
    # Glottal / aspirate
    "HH": "sil",
    # Vowels
    "AA": "aa", "AE": "aa", "AH": "aa", "AW": "aa", "AY": "aa",
    "AO": "O",  "OW": "O",  "OY": "O",
    "EH": "E",  "EY": "E",
    "IH": "I",  "IY": "I",  "Y": "I",
    "UH": "U",  "UW": "U",  "W": "U",
}

# ── 1. Deepgram TTS ──────────────────────────────────────────────────────────
def generate_tts(sentence: str, out_path: Path) -> None:
    # Load API key from .env (or environment)
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DEEPGRAM_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY not found in env or .env")

    print(f"[TTS] Generating audio for: '{sentence}'")
    resp = requests.post(
        "https://api.deepgram.com/v1/speak",
        params={"model": "aura-asteria-en"},
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        json={"text": sentence},
        timeout=30,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    print(f"[TTS] Saved → {out_path}  ({len(resp.content):,} bytes)")


# ── 2. Whisper word-level timestamps ─────────────────────────────────────────
def transcribe(audio_path: Path) -> list[dict]:
    import whisper
    print("[Whisper] Loading model (base)…")
    model = whisper.load_model("base")
    print(f"[Whisper] Transcribing {audio_path}…")
    result = model.transcribe(str(audio_path), word_timestamps=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({
                "word":  w["word"].strip(),
                "start": round(w["start"], 4),
                "end":   round(w["end"],   4),
            })
    print(f"[Whisper] Got {len(words)} words:")
    for w in words:
        print(f"  {w['start']:.3f}s – {w['end']:.3f}s  '{w['word']}'")
    return words


# ── 3. Word → phonemes (CMUdict) ─────────────────────────────────────────────
_CMUDICT = None

def get_cmudict():
    global _CMUDICT
    if _CMUDICT is None:
        nltk.download("cmudict", quiet=True)
        from nltk.corpus import cmudict
        _CMUDICT = cmudict.dict()
    return _CMUDICT

def word_to_phonemes(word: str) -> list[str] | None:
    d = get_cmudict()
    clean = re.sub(r"[^a-z']", "", word.lower())
    entries = d.get(clean)
    if not entries:
        return None
    # Strip stress digits (AA1 → AA)
    return [re.sub(r"\d", "", p) for p in entries[0]]


# ── 4. Build viseme timeline ──────────────────────────────────────────────────
def build_timeline(whisper_words: list[dict], total_duration_s: float) -> list[dict]:
    """
    For each word distribute phonemes uniformly across the word's time span.
    Gaps between words are filled with 'sil'.
    """
    timeline = []
    prev_end_ms = 0

    for w in whisper_words:
        start_ms = int(w["start"] * 1000)
        end_ms   = int(w["end"]   * 1000)

        # Gap before this word → silence
        if start_ms > prev_end_ms:
            timeline.append({"viseme": "sil", "start_ms": prev_end_ms, "end_ms": start_ms})

        phonemes = word_to_phonemes(w["word"])
        if not phonemes:
            # Unknown word → silence for its duration
            timeline.append({"viseme": "sil", "start_ms": start_ms, "end_ms": end_ms})
        else:
            dur_per = (end_ms - start_ms) / len(phonemes)
            for i, ph in enumerate(phonemes):
                viseme = PHONEME_TO_VISEME.get(ph, "sil")
                timeline.append({
                    "viseme":   viseme,
                    "start_ms": int(start_ms + i * dur_per),
                    "end_ms":   int(start_ms + (i + 1) * dur_per),
                })

        prev_end_ms = end_ms

    # Trailing silence
    total_ms = int(total_duration_s * 1000)
    if prev_end_ms < total_ms:
        timeline.append({"viseme": "sil", "start_ms": prev_end_ms, "end_ms": total_ms})

    return timeline


# ── 5. Write JS data file ─────────────────────────────────────────────────────
def write_js_data(sentence: str, audio_path: Path, timeline: list[dict], out_path: Path) -> None:
    # Path relative to demo.html (which lives at repo root)
    audio_rel = str(audio_path.relative_to(Path(__file__).parent.parent))
    data = {
        "sentence": sentence,
        "audio":    audio_rel,
        "timeline": timeline,
    }
    js = f"window.LIPSYNC_DATA = {json.dumps(data, indent=2)};\n"
    out_path.write_text(js)
    print(f"[Data] Saved → {out_path}  ({len(timeline)} viseme frames)")


# ── 6. Get audio duration via ffprobe (fallback: whisper result) ──────────────
def audio_duration(audio_path: Path) -> float:
    import subprocess, shutil
    if shutil.which("ffprobe"):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True
        )
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    # Fallback: read with whisper helper
    import whisper
    audio = whisper.load_audio(str(audio_path))
    return len(audio) / whisper.audio.SAMPLE_RATE


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Optional: override the sentence from the command line (non-flag args).
    global SENTENCE
    free = [a for a in sys.argv[1:] if not a.startswith("--")]
    if free:
        SENTENCE = " ".join(free)

    # 1. TTS
    if "--skip-tts" not in sys.argv:
        generate_tts(SENTENCE, AUDIO_PATH)
    else:
        print(f"[TTS] Skipping (--skip-tts), using existing {AUDIO_PATH}")

    # 2. Whisper
    words = transcribe(AUDIO_PATH)

    # 3 + 4. Phonemes → viseme timeline
    duration = audio_duration(AUDIO_PATH)
    print(f"[Audio] Duration: {duration:.2f}s")
    timeline = build_timeline(words, duration)

    # 5. Write JS
    write_js_data(SENTENCE, AUDIO_PATH, timeline, DATA_PATH)

    print("\n✓ Pipeline complete.")
    print(f"  Audio:    {AUDIO_PATH}")
    print(f"  JS data:  {DATA_PATH}")
    print(f"  Frames:   {len(timeline)}")


if __name__ == "__main__":
    main()
