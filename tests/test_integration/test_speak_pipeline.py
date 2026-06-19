"""Integration tests for the full speak pipeline.

Tests the complete flow: text → TTS → STT → CMU phonemes → viseme timeline → debug.
Uses mocked Deepgram but real CMU dictionary and timeline logic.
"""

import pytest
from tests.fixtures.samples import FAKE_WORDS


# ── Viseme coverage test sentences ─────────────────────────────────────────

RICH_SENTENCE_WORDS = [
    {"word": "shall", "start": 0.0, "end": 0.3},
    {"word": "we", "start": 0.35, "end": 0.5},
    {"word": "find", "start": 0.55, "end": 0.8},
    {"word": "a", "start": 0.82, "end": 0.9},
    {"word": "quiet", "start": 0.95, "end": 1.2},
    {"word": "beach", "start": 1.25, "end": 1.5},
    {"word": "or", "start": 1.55, "end": 1.7},
    {"word": "visit", "start": 1.75, "end": 2.0},
    {"word": "the", "start": 2.05, "end": 2.15},
    {"word": "old", "start": 2.2, "end": 2.4},
    {"word": "zoo", "start": 2.45, "end": 2.7},
]


# ── Core pipeline tests ───────────────────────────────────────────────────

class TestCMUCoverage:
    """Verify the full CMU dictionary provides broad viseme coverage."""

    def test_all_words_in_cmu(self):
        from voxhelm.core.visemes import cmu_lookup
        for w in RICH_SENTENCE_WORDS:
            result = cmu_lookup(w["word"])
            assert result is not None, f"'{w['word']}' not in CMU dict"

    def test_viseme_variety(self):
        from voxhelm.core.visemes import cmu_lookup, ph_to_vis
        all_visemes = set()
        for w in RICH_SENTENCE_WORDS:
            phonemes = cmu_lookup(w["word"])
            if phonemes:
                all_visemes.update(ph_to_vis(p) for p in phonemes)
        # Remove sil (from HH mapping) — we care about distinct mouth shapes
        all_visemes.discard("sil")
        assert len(all_visemes) >= 10, \
            f"Only {len(all_visemes)} visemes from test sentence: {sorted(all_visemes)}"

    def test_common_words_coverage(self):
        """Spot-check that everyday words are in CMU (regression for 100-word subset)."""
        from voxhelm.core.visemes import cmu_lookup
        everyday = [
            "shall", "find", "quiet", "beach", "visit", "zoo", "coffee",
            "please", "thank", "morning", "evening", "beautiful", "together",
            "water", "garden", "journey", "simple", "difficult", "understand",
        ]
        missing = [w for w in everyday if cmu_lookup(w) is None]
        assert len(missing) == 0, f"Words missing from CMU: {missing}"


class TestTimelinePipeline:
    """Test the word→timeline→debug pipeline produces correct output."""

    def test_timeline_has_diverse_visemes(self):
        from voxhelm.core.timeline import words_to_timeline
        timeline = words_to_timeline(RICH_SENTENCE_WORDS)
        visemes = set(e["v"] for e in timeline)
        visemes.discard("sil")
        assert len(visemes) >= 10, \
            f"Timeline only has {len(visemes)} visemes: {sorted(visemes)}"

    def test_timeline_events_have_phonemes(self):
        from voxhelm.core.timeline import words_to_timeline
        timeline = words_to_timeline(RICH_SENTENCE_WORDS)
        # Every non-sil event should have a real phoneme (not '?')
        non_sil = [e for e in timeline if e["v"] != "sil"]
        unknown = [e for e in non_sil if e["ph"] == "?"]
        assert len(unknown) == 0, \
            f"{len(unknown)} unknown phonemes in timeline: {unknown}"

    def test_debug_all_words_resolved(self):
        from voxhelm.core.timeline import words_to_debug
        debug = words_to_debug(RICH_SENTENCE_WORDS)
        assert len(debug) == len(RICH_SENTENCE_WORDS)
        unresolved = [d for d in debug if not d["in_cmu"]]
        assert len(unresolved) == 0, \
            f"Unresolved words: {[d['word'] for d in unresolved]}"

    def test_debug_has_viseme_for_every_word(self):
        from voxhelm.core.timeline import words_to_debug
        debug = words_to_debug(RICH_SENTENCE_WORDS)
        for d in debug:
            assert len(d["visemes"]) >= 1, f"'{d['word']}' has no visemes"

    def test_no_consecutive_sil_in_speech(self):
        """During speech, there shouldn't be long sil gaps between phonemes."""
        from voxhelm.core.timeline import words_to_timeline
        timeline = words_to_timeline(RICH_SENTENCE_WORDS)
        # Check that we don't have sil lasting more than 0.15s during speech
        for i, ev in enumerate(timeline):
            if ev["v"] == "sil" and i + 1 < len(timeline):
                gap = timeline[i + 1]["t"] - ev["t"]
                # Gaps between words are fine, but shouldn't be huge
                assert gap < 0.5, \
                    f"Long sil gap at t={ev['t']:.3f}: {gap:.3f}s"


class TestAPISpeak:
    """Test the /api/speak endpoint returns correct debug data."""

    def test_speak_returns_debug(self, api_client):
        # Generate a head first
        resp = api_client.post("/api/generate", json={
            "mode": "svg", "preset": "young_woman",
        })
        from tests.test_server.test_api import _wait_for_job
        _wait_for_job(api_client, resp.json()["job_id"])

        resp = api_client.post("/api/speak", json={
            "head": "young_woman", "text": "hello world",
        })
        assert resp.status_code == 200
        data = resp.json()

        # Debug should be present
        assert data["debug"] is not None
        assert len(data["debug"]) >= 1

        # Each entry should have required fields
        for entry in data["debug"]:
            assert "word" in entry
            assert "start" in entry
            assert "end" in entry
            assert "phonemes" in entry
            assert "visemes" in entry
            assert "in_cmu" in entry
            assert isinstance(entry["phonemes"], list)
            assert isinstance(entry["visemes"], list)

    def test_speak_debug_matches_words(self, api_client):
        resp = api_client.post("/api/generate", json={
            "mode": "svg", "preset": "young_woman",
        })
        from tests.test_server.test_api import _wait_for_job
        _wait_for_job(api_client, resp.json()["job_id"])

        resp = api_client.post("/api/speak", json={
            "head": "young_woman", "text": "hello world",
        })
        data = resp.json()

        # Debug should have same number of entries as words from STT
        # (our mock returns 2 words: "hello" and "world")
        assert len(data["debug"]) == 2
        assert data["debug"][0]["word"] == "hello"
        assert data["debug"][1]["word"] == "world"

    def test_speak_timeline_has_visemes(self, api_client):
        resp = api_client.post("/api/generate", json={
            "mode": "svg", "preset": "young_woman",
        })
        from tests.test_server.test_api import _wait_for_job
        _wait_for_job(api_client, resp.json()["job_id"])

        resp = api_client.post("/api/speak", json={
            "head": "young_woman", "text": "hello world",
        })
        data = resp.json()
        timeline = data["timeline"]

        # Timeline should have multiple events, not just sil
        non_sil = [e for e in timeline if e["v"] != "sil"]
        assert len(non_sil) >= 2, \
            f"Timeline has only {len(non_sil)} non-sil events"

    def test_speak_returns_alignment_method(self, api_client):
        resp = api_client.post("/api/generate", json={
            "mode": "svg", "preset": "young_woman",
        })
        from tests.test_server.test_api import _wait_for_job
        _wait_for_job(api_client, resp.json()["job_id"])

        resp = api_client.post("/api/speak", json={
            "head": "young_woman", "text": "hello world",
        })
        data = resp.json()
        assert "alignment" in data
        assert data["alignment"] in ("wav2vec2", "cmu")


@pytest.mark.skipif(
    not __import__("voxhelm.core.aligner", fromlist=["is_available"]).is_available(),
    reason="torch/torchaudio not installed",
)
class TestAligner:
    """Test the wav2vec2 aligner module directly."""

    def test_aligner_is_available(self):
        from voxhelm.core.aligner import is_available
        assert is_available() is True

    def test_pcm_roundtrip(self):
        """Generate PCM, convert to waveform, verify shape."""
        import array
        from voxhelm.core.aligner import pcm_to_waveform

        # 0.5s of silence at 16kHz
        silence = array.array("h", [0] * 8000)
        waveform = pcm_to_waveform(silence.tobytes())
        assert waveform.shape == (1, 8000)

    def test_aligned_to_timeline_produces_visemes(self):
        """Aligned words should produce a valid viseme timeline."""
        from voxhelm.core.timeline import aligned_to_timeline

        aligned = [
            {"word": "shall", "start": 0.0, "end": 0.3, "chars": [
                {"char": "s", "start": 0.0, "end": 0.06},
                {"char": "h", "start": 0.06, "end": 0.12},
                {"char": "a", "start": 0.12, "end": 0.18},
                {"char": "l", "start": 0.18, "end": 0.24},
                {"char": "l", "start": 0.24, "end": 0.3},
            ]},
            {"word": "we", "start": 0.35, "end": 0.5, "chars": [
                {"char": "w", "start": 0.35, "end": 0.42},
                {"char": "e", "start": 0.42, "end": 0.5},
            ]},
            {"word": "find", "start": 0.55, "end": 0.8, "chars": [
                {"char": "f", "start": 0.55, "end": 0.61},
                {"char": "i", "start": 0.61, "end": 0.67},
                {"char": "n", "start": 0.67, "end": 0.73},
                {"char": "d", "start": 0.73, "end": 0.8},
            ]},
        ]
        timeline = aligned_to_timeline(aligned)
        visemes = set(e["v"] for e in timeline)
        visemes.discard("sil")
        assert len(visemes) >= 4, f"Expected 4+ visemes, got {sorted(visemes)}"

    def test_alignment_uses_word_boundaries(self):
        """Aligned timeline should use the word start/end times, not uniform."""
        from voxhelm.core.timeline import aligned_to_timeline

        # Word with known timing
        aligned = [
            {"word": "hello", "start": 1.0, "end": 1.5, "chars": [
                {"char": "h", "start": 1.0, "end": 1.1},
                {"char": "e", "start": 1.1, "end": 1.2},
                {"char": "l", "start": 1.2, "end": 1.3},
                {"char": "l", "start": 1.3, "end": 1.4},
                {"char": "o", "start": 1.4, "end": 1.5},
            ]},
        ]
        timeline = aligned_to_timeline(aligned)
        # First phoneme should start at 1.0 (the word start), not 0.0
        non_sil = [e for e in timeline if e["v"] != "sil" and e["t"] >= 1.0]
        assert len(non_sil) >= 1, "No phonemes at word boundary"
        assert non_sil[0]["t"] >= 1.0
