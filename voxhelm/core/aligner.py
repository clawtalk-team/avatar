"""Wav2Vec2-based forced alignment using torchaudio MMS_FA.

Aligns audio to a transcript at character level, producing precise
timing for each character. Combined with CMU dict phonemes, this gives
much better viseme timing than uniform distribution.

The MMS_FA model outputs character-level alignments (a-z), not phonemes.
We use these to:
  1. Get precise word boundary timing
  2. Proportionally distribute phonemes within words based on
     actual speech timing (not uniform)

Usage:
    from voxhelm.core.aligner import align_audio, is_available

    if is_available():
        aligned = align_audio(audio_bytes, "hello world")
        # Returns word-level data with character timing
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_model_cache = None


def is_available() -> bool:
    """Check if torch and torchaudio are installed for forced alignment."""
    try:
        import torch
        import torchaudio
        return hasattr(torchaudio.functional, 'forced_align')
    except ImportError:
        return False


def _get_model():
    """Load and cache the MMS forced alignment model."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    import torch
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model()
    model.eval()
    labels = bundle.get_labels()
    label_to_idx = {l: i for i, l in enumerate(labels)}
    sample_rate = bundle.sample_rate

    _model_cache = (model, labels, label_to_idx, sample_rate)
    return _model_cache


def pcm_to_waveform(pcm_bytes: bytes, sample_rate: int = 16000):
    """Convert raw PCM16 bytes to a torch tensor.

    Args:
        pcm_bytes: Raw 16-bit signed little-endian PCM audio.
        sample_rate: Sample rate of the PCM data (must match model's expected rate).

    Returns:
        Torch tensor of shape (1, num_samples), float32, range [-1, 1].
    """
    import array
    import torch

    samples = array.array("h", pcm_bytes)  # 16-bit signed
    waveform = torch.tensor(samples, dtype=torch.float32).unsqueeze(0) / 32768.0
    return waveform


def _audio_to_waveform(audio_bytes: bytes, target_sr: int):
    """Convert audio bytes to a torch tensor.

    Accepts raw PCM16 (preferred, no dependencies) or MP3 (requires ffmpeg).
    PCM16 is detected by absence of MP3/WAV headers.
    """
    import torch

    # Check if it's MP3 (starts with ID3 or 0xFF sync)
    is_mp3 = audio_bytes[:3] == b"ID3" or (len(audio_bytes) > 1 and audio_bytes[0] == 0xFF)
    # Check if it's WAV (starts with RIFF)
    is_wav = audio_bytes[:4] == b"RIFF"

    if not is_mp3 and not is_wav:
        # Assume raw PCM16 at the target sample rate
        return pcm_to_waveform(audio_bytes, target_sr)

    # For MP3/WAV, use ffmpeg to convert
    import subprocess

    with tempfile.NamedTemporaryFile(
        suffix=".mp3" if is_mp3 else ".wav", delete=False
    ) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_path, "-ar", str(target_sr),
             "-ac", "1", "-f", "s16le", "-acodec", "pcm_s16le", "-"],
            capture_output=True, check=True,
        )
        return pcm_to_waveform(result.stdout, target_sr)
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found — required for MP3/WAV conversion. "
            "Use encoding='linear16' in deepgram_tts() to get raw PCM instead."
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def align_audio(audio_bytes: bytes, transcript: str) -> list[dict]:
    """Align audio to transcript using wav2vec2 forced alignment.

    Returns word-level segments with character-level timing detail.

    Args:
        audio_bytes: MP3 or WAV audio bytes.
        transcript: Text transcript of the audio.

    Returns:
        List of {word, start, end, chars: [{char, start, end}]} dicts.
    """
    import torch
    import torchaudio

    model, labels, label_to_idx, sample_rate = _get_model()

    # Convert audio
    waveform = _audio_to_waveform(audio_bytes, sample_rate)
    duration = waveform.shape[1] / sample_rate

    # Clean transcript to match model's label set (a-z only)
    clean_text = re.sub(r"[^a-z ]", "", transcript.lower())
    words = clean_text.split()

    # Build flat token sequence (no spaces — model uses blank token for boundaries)
    flat_chars = "".join(words)
    tokens = [label_to_idx.get(c, 0) for c in flat_chars]

    if not tokens:
        log.warning("No valid tokens from transcript: %s", transcript[:60])
        return []

    # Run forced alignment
    with torch.no_grad():
        emission, _ = model(waveform)

    token_tensor = torch.tensor([tokens], dtype=torch.int32)
    aligned_tokens, scores = torchaudio.functional.forced_align(
        emission, token_tensor, blank=0
    )

    # Convert frame indices to timestamps
    num_frames = emission.shape[1]
    frame_dur = duration / num_frames

    aligned = aligned_tokens[0].tolist()

    # Group frames into character segments
    char_segments = []
    current_token = None
    start_frame = 0
    token_counter = -1  # tracks which input token we're on

    for frame_idx, token_idx in enumerate(aligned):
        if token_idx != current_token:
            if current_token is not None and current_token != 0:
                char_segments.append({
                    "token_idx": token_counter,
                    "start": round(start_frame * frame_dur, 4),
                    "end": round(frame_idx * frame_dur, 4),
                })
            if token_idx != 0:
                token_counter += 1
            current_token = token_idx
            start_frame = frame_idx

    # Last segment
    if current_token is not None and current_token != 0:
        char_segments.append({
            "token_idx": token_counter,
            "start": round(start_frame * frame_dur, 4),
            "end": round(len(aligned) * frame_dur, 4),
        })

    # Map character segments back to words
    char_offset = 0
    result = []
    for word in words:
        word_chars = []
        for i, c in enumerate(word):
            seg_idx = char_offset + i
            if seg_idx < len(char_segments):
                seg = char_segments[seg_idx]
                word_chars.append({
                    "char": c,
                    "start": seg["start"],
                    "end": seg["end"],
                })
        char_offset += len(word)

        if word_chars:
            result.append({
                "word": word,
                "start": word_chars[0]["start"],
                "end": word_chars[-1]["end"],
                "chars": word_chars,
            })

    log.info("Aligned %d words, %d chars from %.1fs audio",
             len(result), len(char_segments), duration)

    return result
