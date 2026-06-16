"""Audio generation and speech-to-text via Deepgram."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

log = logging.getLogger(__name__)


def deepgram_tts(text: str, api_key: str | None = None) -> bytes:
    """Generate speech audio (MP3) from text via Deepgram TTS.

    Args:
        text: Text to speak.
        api_key: Deepgram API key (defaults to DEEPGRAM_API_KEY env var).

    Returns:
        MP3 audio bytes.
    """
    key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY not set")

    url = "https://api.deepgram.com/v1/speak?model=aura-2-thalia-en&encoding=mp3"
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Token {key}")
    req.add_header("Content-Type", "application/json")

    log.info("TTS: %s...", text[:60])
    with urllib.request.urlopen(req, timeout=30) as resp:
        audio = resp.read()
    log.info("TTS OK (%d bytes)", len(audio))
    return audio


def deepgram_stt_words(audio: bytes, api_key: str | None = None) -> list[dict]:
    """Run speech-to-text on audio bytes, returning word-level timestamps.

    Args:
        audio: MP3 audio bytes.
        api_key: Deepgram API key (defaults to DEEPGRAM_API_KEY env var).

    Returns:
        List of {word, start, end} dicts with timestamps in seconds.
    """
    key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY not set")

    url = "https://api.deepgram.com/v1/listen?model=nova-3&punctuate=false&words=true"
    req = urllib.request.Request(url, data=audio, method="POST")
    req.add_header("Authorization", f"Token {key}")
    req.add_header("Content-Type", "audio/mpeg")

    log.info("STT alignment...")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    words = data["results"]["channels"][0]["alternatives"][0].get("words", [])
    log.info("STT OK (%d words)", len(words))
    return words
