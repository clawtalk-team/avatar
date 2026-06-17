"""Test fixtures — sample data for mocking external APIs."""

# Minimal valid SVG (512x512 viewBox, simple circle face)
SAMPLE_SVG = (
    '<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="256" cy="256" r="200" fill="#F5C5A3"/>'
    '<circle cx="210" cy="220" r="20" fill="#333"/>'
    '<circle cx="302" cy="220" r="20" fill="#333"/>'
    '<path d="M 210 320 Q 256 350 302 320" stroke="#333" fill="none" stroke-width="4"/>'
    '</svg>'
)

# Minimal 1x1 transparent PNG (68 bytes)
MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

# Fake MP3 bytes (just a header — not playable but non-empty)
FAKE_MP3 = b'\xff\xfb\x90\x00' + b'\x00' * 100

# Fake Deepgram STT word response
FAKE_WORDS = [
    {"word": "hello", "start": 0.0, "end": 0.4},
    {"word": "world", "start": 0.5, "end": 0.9},
]
