#!/usr/bin/env python3
"""
viseme_demo.py  —  audio-synced SVG viseme animation demo
----------------------------------------------------------
1. Generates TTS audio via Deepgram for each sentence
2. Gets real word timestamps via Deepgram STT
3. Distributes phonemes within each word's time window
4. Writes a self-contained HTML player with speed controls

Usage:
  python scripts/viseme_demo.py --svg-dir outputs/svg_claude --out outputs/viseme_demo.html
"""

import argparse, base64, json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Load .env
env_file = REPO_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

# ─── Phoneme → Viseme ────────────────────────────────────────────────────────

PHONEME_TO_VISEME = {
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

def ph_to_vis(ph):
    base = re.sub(r"\d", "", ph)
    return PHONEME_TO_VISEME.get(ph, PHONEME_TO_VISEME.get(base, "sil"))

# ─── CMU dict (subset) ───────────────────────────────────────────────────────

CMU = {
    "the":["DH","AH0"], "quick":["K","W","IH1","K"], "brown":["B","R","AW1","N"],
    "fox":["F","AA1","K","S"], "jumps":["JH","AH1","M","P","S"],
    "over":["OW1","V","ER0"], "five":["F","AY1","V"], "lazy":["L","EY1","Z","IY0"],
    "dogs":["D","AO1","G","Z"], "but":["B","AH1","T"], "they":["DH","EY1"],
    "should":["SH","UH1","D"], "also":["AO1","L","S","OW0"], "be":["B","IY1"],
    "very":["V","EH1","R","IY0"], "happy":["HH","AE1","P","IY0"],
    "talking":["T","AO1","K","IH0","NG"], "with":["W","IH1","DH"],
    "people":["P","IY1","P","AH0","L"], "hello":["HH","AH0","L","OW1"],
    "world":["W","ER1","L","D"], "how":["HH","AW1"], "are":["AA1","R"],
    "you":["Y","UW1"], "today":["T","AH0","D","EY1"], "i":["AY1"],
    "am":["AE1","M"], "doing":["D","UW1","IH0","NG"], "well":["W","EH1","L"],
    "thank":["TH","AE1","NG","K"], "thanks":["TH","AE1","NG","K","S"],
    "and":["AE1","N","D"], "of":["AH0","V"], "to":["T","UW1"], "a":["AH0"],
    "is":["IH1","Z"], "in":["IH0","N"], "it":["IH1","T"], "that":["DH","AE1","T"],
    "this":["DH","IH1","S"], "my":["M","AY1"], "your":["Y","AO1","R"],
    "all":["AO1","L"], "have":["HH","AE1","V"], "for":["F","AO1","R"],
    "on":["AO1","N"], "can":["K","AE1","N"], "not":["N","AA1","T"],
    "will":["W","IH1","L"], "what":["W","AH1","T"], "so":["S","OW1"],
    "know":["N","OW1"], "go":["G","OW1"], "love":["L","AH1","V"],
    "some":["S","AH1","M"], "time":["T","AY1","M"], "good":["G","UH1","D"],
    "now":["N","AW1"], "think":["TH","IH1","NG","K"], "just":["JH","AH1","S","T"],
    "one":["W","AH1","N"], "up":["AH1","P"], "out":["AW1","T"], "no":["N","OW1"],
    "at":["AE1","T"], "an":["AE1","N"], "do":["D","UW1"], "call":["K","AO1","L"],
    "choose":["CH","UW1","Z"], "sharing":["SH","EH1","R","IH0","NG"],
    "books":["B","UH1","K","S"], "red":["R","EH1","D"], "big":["B","IH1","G"],
    "eight":["EY1","T"], "every":["EH1","V","R","IY0"], "say":["S","EY1"],
    "says":["S","EH1","Z"], "through":["TH","R","UW1"], "three":["TH","R","IY1"],
    "many":["M","EH1","N","IY0"], "new":["N","UW1"], "way":["W","EY1"],
    "see":["S","IY1"], "make":["M","EY1","K"], "come":["K","AH1","M"],
    "look":["L","UH1","K"], "more":["M","AO1","R"], "get":["G","EH1","T"],
    "like":["L","AY1","K"], "him":["HH","IH1","M"], "his":["HH","IH1","Z"],
    "from":["F","R","AH1","M"], "then":["DH","EH1","N"], "there":["DH","EH1","R"],
    "these":["DH","IY1","Z"], "those":["DH","OW1","Z"], "use":["Y","UW1","Z"],
    "each":["IY1","CH"], "which":["W","IH1","CH"], "their":["DH","EH1","R"],
    "talk":["T","AO1","K"], "speech":["S","P","IY1","CH"],
    "voice":["V","OY1","S"], "face":["F","EY1","S"], "mouth":["M","AW1","TH"],
    "lip":["L","IH1","P"], "lips":["L","IH1","P","S"],
    "show":["SH","OW1"], "shape":["SH","EY1","P"],
    "different":["D","IH1","F","R","AH0","N","T"],
    "when":["W","EH1","N"], "each":["IY1","CH"],
    "phoneme":["F","OW1","N","IY0","M"],
    "changes":["CH","EY1","N","JH","AH0","Z"],
    "watch":["W","AO1","CH"],
    "carefully":["K","EH1","R","F","AH0","L","IY0"],
    "as":["AE1","Z"],
    "moves":["M","UW1","V","Z"],
    "between":["B","IH0","T","W","IY1","N"],
    "position":["P","AH0","Z","IH1","SH","AH0","N"],
    "positions":["P","AH0","Z","IH1","SH","AH0","N","Z"],
    "notice":["N","OW1","T","IH0","S"],
    "open":["OW1","P","AH0","N"],
    "close":["K","L","OW1","Z"],
    "round":["R","AW1","N","D"],
    "spread":["S","P","R","EH1","D"],
    "jaw":["JH","AO1"],
    "drops":["D","R","AA1","P","S"],
    "wider":["W","AY1","D","ER0"],
}

# ─── Deepgram API ─────────────────────────────────────────────────────────────

def deepgram_tts(text: str, api_key: str) -> bytes:
    url = "https://api.deepgram.com/v1/speak?model=aura-2-thalia-en&encoding=mp3"
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Token {api_key}")
    req.add_header("Content-Type", "application/json")
    print(f"  TTS: {text[:60]}...", end=" ", flush=True)
    with urllib.request.urlopen(req, timeout=30) as resp:
        audio = resp.read()
    print(f"OK ({len(audio):,} bytes)")
    return audio


def deepgram_stt_words(audio: bytes, api_key: str) -> list[dict]:
    """Run STT on MP3 bytes, return word list with start/end timestamps."""
    url = "https://api.deepgram.com/v1/listen?model=nova-3&punctuate=false&words=true"
    req = urllib.request.Request(url, data=audio, method="POST")
    req.add_header("Authorization", f"Token {api_key}")
    req.add_header("Content-Type", "audio/mpeg")
    print("  STT alignment...", end=" ", flush=True)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    words = data["results"]["channels"][0]["alternatives"][0].get("words", [])
    print(f"OK ({len(words)} words)")
    return words


def words_to_timeline(words: list[dict]) -> list[dict]:
    """
    Convert Deepgram word timestamps to phoneme/viseme timeline.
    Each word's phonemes are distributed evenly within [word.start, word.end].
    """
    timeline = [{"t": 0.0, "v": "sil", "ph": "SIL"}]

    for w in words:
        word_text = re.sub(r"[^a-z']", "", w["word"].lower())
        start = w["start"]
        end = w["end"]
        dur = max(end - start, 0.01)

        phonemes = CMU.get(word_text, None)
        if not phonemes:
            # Unknown word: show aa for vowel-ish duration, sil otherwise
            timeline.append({"t": round(start, 4), "v": "aa", "ph": "?"})
            timeline.append({"t": round(end, 4), "v": "sil", "ph": "SIL"})
            continue

        ph_dur = dur / len(phonemes)
        for i, ph in enumerate(phonemes):
            t = start + i * ph_dur
            timeline.append({"t": round(t, 4), "v": ph_to_vis(ph), "ph": ph})

        # Brief silence after word
        timeline.append({"t": round(end, 4), "v": "sil", "ph": "SIL"})

    # Deduplicate consecutive same-viseme entries
    deduped = [timeline[0]]
    for entry in timeline[1:]:
        if entry["v"] != deduped[-1]["v"] or entry["t"] > deduped[-1]["t"] + 0.02:
            deduped.append(entry)

    return deduped


# ─── SVG loading ─────────────────────────────────────────────────────────────

def load_svgs(svg_dir: Path) -> dict[str, str]:
    all_visemes = ["sil","PP","FF","TH","DD","kk","CH","SS","nn","RR","aa","E","I","O","U"]
    svgs = {}
    for v in all_visemes:
        f = svg_dir / f"{v}.svg"
        if f.exists():
            content = re.sub(r'<\?xml[^?]*\?>', '', f.read_text()).strip()
            svgs[v] = content
    return svgs


# ─── HTML writer ──────────────────────────────────────────────────────────────

def write_demo_html(sentences: list[dict], svgs: dict[str, str], out_path: Path):
    """
    sentences: list of {text, audio_b64, timeline}
    """
    all_visemes = sorted(set(
        e["v"] for s in sentences for e in s["timeline"] if e["v"] != "sil"
    ))

    # Escape </script> sequences in JSON data to avoid breaking the HTML script tag
    def safe_json(obj):
        return json.dumps(obj).replace("</", "<\\/")

    svgs_json = safe_json({v: svgs.get(v, svgs.get("sil", "")) for v in list(svgs.keys())})
    sentences_json = safe_json([
        {"text": s["text"], "audio": s["audio_b64"], "timeline": s["timeline"]}
        for s in sentences
    ])

    cards = "".join(
        f'<div class="sent-btn" id="btn-{i}" onclick="loadSentence({i})">{s["text"][:55]}{"…" if len(s["text"])>55 else ""}</div>'
        for i, s in enumerate(sentences)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>ClaWTalk Viseme Demo</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#111;color:#eee;font-family:system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;padding:32px 20px;min-height:100vh;gap:0}}
  h1{{font-size:20px;color:#fff;margin-bottom:4px}}
  .sub{{font-size:12px;color:#555;margin-bottom:20px}}
  .stage{{width:320px;height:320px;background:#1a1a1a;border-radius:18px;overflow:hidden;position:relative;border:1px solid #2a2a2a;flex-shrink:0}}
  .stage svg{{width:100%;height:100%;position:absolute;top:0;left:0;display:none}}
  #blink-overlay{{display:block;width:100%;height:100%;position:absolute;top:0;left:0;pointer-events:none;z-index:10}}
  .eyelid{{transform-origin:top center;transform:scaleY(0);transition:transform 0s}}
  .vis-label{{margin-top:12px;font-size:26px;font-weight:700;color:#7cf;min-height:34px;letter-spacing:1px}}
  .ph-label{{font-size:12px;color:#555;margin-top:3px;min-height:18px;font-family:monospace}}
  .sent-list{{display:flex;flex-direction:column;gap:6px;margin:16px 0;width:100%;max-width:500px}}
  .sent-btn{{padding:8px 14px;background:#1e1e1e;border:1px solid #333;border-radius:8px;font-size:13px;color:#aaa;cursor:pointer;text-align:left;transition:background .15s,border-color .15s}}
  .sent-btn:hover{{background:#2a2a2a;border-color:#444}}
  .sent-btn.active{{background:#1a3a2a;border-color:#2a6;color:#cfc}}
  .controls{{display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap;justify-content:center}}
  .play-btn{{background:#2a6;color:#fff;border:none;padding:9px 26px;border-radius:8px;font-size:15px;cursor:pointer;font-weight:600}}
  .play-btn:hover{{background:#3b7}}
  .play-btn:disabled{{background:#333;cursor:default;color:#666}}
  .speed-group{{display:flex;gap:4px}}
  .spd-btn{{background:#222;color:#888;border:1px solid #333;padding:6px 14px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:500}}
  .spd-btn:hover{{background:#2a2a2a}}
  .spd-btn.active{{background:#1a3050;border-color:#37f;color:#7af}}
  .progress{{width:360px;height:5px;background:#222;border-radius:3px;overflow:hidden;margin-top:14px}}
  .progress-bar{{height:100%;background:#2a6;width:0%}}
  .text-box{{max-width:440px;text-align:center;font-size:14px;color:#888;line-height:1.6;min-height:44px;margin-top:14px}}
  .chip-row{{display:flex;flex-wrap:wrap;gap:5px;max-width:460px;justify-content:center;margin-top:14px}}
  .chip{{padding:3px 9px;border-radius:12px;font-size:11px;font-weight:600;background:#1e1e1e;color:#666;border:1px solid #2a2a2a;font-family:monospace;transition:all .1s}}
  .chip.active{{background:#1a3a2a;color:#4f9;border-color:#2a6}}
</style>
</head>
<body>
<h1>ClaWTalk SVG Viseme Demo</h1>
<p class="sub">Deepgram TTS + word-aligned phonemes · 15 visemes · Claude-generated faces</p>

<div class="stage" id="stage">
  <!-- Blink overlay: skin-coloured ellipses exactly matching the eye-white ellipses.
       Animate ry from 0→28 to close the eye. No transforms needed. -->
  <svg id="blink-overlay" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
    <!-- Left eyelid (matches eye white at cx=210 cy=240 rx=30 ry=28) -->
    <ellipse id="lid-l" cx="210" cy="240" rx="30" ry="0"
             fill="#F5C4A1" stroke="#3D2B1F" stroke-width="2"/>
    <!-- Right eyelid (matches eye white at cx=302 cy=240 rx=30 ry=28) -->
    <ellipse id="lid-r" cx="302" cy="240" rx="30" ry="0"
             fill="#F5C4A1" stroke="#3D2B1F" stroke-width="2"/>
  </svg>
</div>

<div class="vis-label" id="vis-label">sil</div>
<div class="ph-label" id="ph-label">ready</div>

<div class="sent-list">{cards}</div>

<div class="controls">
  <button class="play-btn" id="play-btn" onclick="playDemo()" disabled>▶ Play</button>
  <div class="speed-group">
    <button class="spd-btn" onclick="setSpeed(0.25)">0.25×</button>
    <button class="spd-btn" onclick="setSpeed(0.5)">0.5×</button>
    <button class="spd-btn active" id="spd-1" onclick="setSpeed(1)">1×</button>
  </div>
</div>

<div class="progress"><div class="progress-bar" id="pbar"></div></div>
<div class="text-box" id="text-box">Select a sentence above to begin.</div>

<div class="chip-row" id="chips">
  {"".join(f'<div class="chip" id="chip-{v}">{v}</div>' for v in all_visemes)}
</div>

<audio id="audio" preload="auto"></audio>

<script>
const SVGS = {svgs_json};
const SENTENCES = {sentences_json};

const stage = document.getElementById('stage');
const audio = document.getElementById('audio');
const playBtn = document.getElementById('play-btn');
const pbar = document.getElementById('pbar');
const visLabel = document.getElementById('vis-label');
const phLabel = document.getElementById('ph-label');
const textBox = document.getElementById('text-box');

// Inject SVGs
const svgEls = {{}};
for (const [v, svg] of Object.entries(SVGS)) {{
  const tmp = document.createElement('div');
  tmp.innerHTML = svg;
  const el = tmp.firstElementChild;
  if (el) {{ el.id = 'svg-' + v; stage.appendChild(el); svgEls[v] = el; }}
}}

let curViseme = 'sil';
function showViseme(v) {{
  if (!svgEls[v]) v = 'sil';
  if (v === curViseme) return;
  if (svgEls[curViseme]) svgEls[curViseme].style.display = 'none';
  if (svgEls[v]) svgEls[v].style.display = 'block';
  curViseme = v;
  visLabel.textContent = v;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  const chip = document.getElementById('chip-' + v);
  if (chip) chip.classList.add('active');
}}
if (svgEls['sil']) svgEls['sil'].style.display = 'block';

let curTimeline = [];
let curSpeed = 1;

function getVisemeAt(t) {{
  let v = 'sil', ph = 'SIL';
  for (let i = 0; i < curTimeline.length - 1; i++) {{
    if (t >= curTimeline[i].t && t < curTimeline[i+1].t) {{
      v = curTimeline[i].v; ph = curTimeline[i].ph; break;
    }}
  }}
  return [v, ph];
}}

function tick() {{
  const t = audio.currentTime;
  const dur = audio.duration || 1;
  pbar.style.width = (t / dur * 100) + '%';
  const [v, ph] = getVisemeAt(t);
  showViseme(v);
  phLabel.textContent = ph;
  if (!audio.paused && !audio.ended) requestAnimationFrame(tick);
  else if (audio.ended) {{
    showViseme('sil'); phLabel.textContent = ''; playBtn.disabled = false;
    playBtn.textContent = '▶ Play again'; pbar.style.width = '100%';
  }}
}}

function playDemo() {{
  audio.currentTime = 0;
  audio.playbackRate = curSpeed;
  playBtn.disabled = true; playBtn.textContent = '⏸ Playing…';
  audio.play().then(() => requestAnimationFrame(tick));
}}

function setSpeed(s) {{
  curSpeed = s;
  audio.playbackRate = s;
  document.querySelectorAll('.spd-btn').forEach(b => b.classList.remove('active'));
  const labels = {{0.25:'0.25×', 0.5:'0.5×', 1:'1×'}};
  document.querySelectorAll('.spd-btn').forEach(b => {{
    if (b.textContent === labels[s]) b.classList.add('active');
  }});
}}

function loadSentence(i) {{
  audio.pause();
  const s = SENTENCES[i];
  curTimeline = s.timeline;
  const src = 'data:audio/mpeg;base64,' + s.audio;
  audio.src = src;
  audio.load();
  textBox.textContent = s.text;
  pbar.style.width = '0%';
  showViseme('sil'); phLabel.textContent = 'ready';
  playBtn.disabled = false; playBtn.textContent = '▶ Play';
  document.querySelectorAll('.sent-btn').forEach((b,j) => b.classList.toggle('active', j===i));
}}

// Auto-load first sentence on page load
loadSentence(0);

// ── Blink animation ──────────────────────────────────────────────────────────
// Simple: just animate ry of the eyelid ellipses from 0 (open) → 28 (closed).
const lidL = document.getElementById('lid-l');
const lidR = document.getElementById('lid-r');

function setLids(ry) {{
  if (lidL) lidL.setAttribute('ry', ry);
  if (lidR) lidR.setAttribute('ry', ry);
}}

// Single-chain blink scheduler — only ONE timer chain ever runs.
// The old approach called blink() AND scheduled a double-blink, creating two
// independent perpetual loops that multiplied on every double-blink.
const BLINK_STEPS = [0, 7, 14, 21, 28, 28, 21, 14, 7, 0];
const BLINK_STEP_MS = 20; // 200ms total

function runBlink(onDone) {{
  BLINK_STEPS.forEach((ry, i) => setTimeout(() => setLids(ry), i * BLINK_STEP_MS));
  setTimeout(onDone, BLINK_STEPS.length * BLINK_STEP_MS);
}}

function scheduleBlink() {{
  const wait = 4000 + Math.random() * 5000;
  setTimeout(() => {{
    // First blink
    runBlink(() => {{
      if (Math.random() < 0.25) {{
        // Double-blink: one extra 250ms later, then continue the chain
        setTimeout(() => runBlink(scheduleBlink), 250);
      }} else {{
        scheduleBlink(); // back to waiting
      }}
    }});
  }}, wait);
}}

setTimeout(scheduleBlink, 1000 + Math.random() * 2000);
</script>
</body></html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)


# ─── Main ─────────────────────────────────────────────────────────────────────

TEXTS = [
    "The quick brown fox jumps over five lazy dogs, but they should also be very happy talking with people.",
    "Watch carefully as the mouth moves between different positions — notice how the jaw drops wider when each phoneme changes.",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg-dir", default="outputs/svg_claude")
    parser.add_argument("--out", default="outputs/viseme_demo.html")
    parser.add_argument("--regen-audio", action="store_true", help="Re-generate audio even if cached")
    args = parser.parse_args()

    svg_dir = REPO_ROOT / args.svg_dir
    out_path = REPO_ROOT / args.out
    cache_dir = REPO_ROOT / "outputs" / "viseme_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not deepgram_key:
        print("DEEPGRAM_API_KEY not set"); sys.exit(1)

    print(f"Loading SVGs from {svg_dir}...")
    svgs = load_svgs(svg_dir)
    print(f"  Loaded: {sorted(svgs.keys())}")

    sentences = []
    for i, text in enumerate(TEXTS):
        print(f"\nSentence {i+1}: {text[:60]}...")
        slug = re.sub(r"[^a-z0-9]", "_", text[:30].lower())
        audio_cache = cache_dir / f"s{i}_{slug}.mp3"
        tl_cache = cache_dir / f"s{i}_{slug}_timeline.json"

        if audio_cache.exists() and tl_cache.exists() and not args.regen_audio:
            print("  Using cached audio+timeline")
            audio_bytes = audio_cache.read_bytes()
            timeline = json.loads(tl_cache.read_text())
        else:
            audio_bytes = deepgram_tts(text, deepgram_key)
            audio_cache.write_bytes(audio_bytes)
            words = deepgram_stt_words(audio_bytes, deepgram_key)
            timeline = words_to_timeline(words)
            tl_cache.write_text(json.dumps(timeline, indent=2))
            print(f"  Timeline: {len(timeline)} events, {timeline[-1]['t']:.2f}s")

        audio_b64 = base64.b64encode(audio_bytes).decode()
        used = sorted(set(e["v"] for e in timeline))
        print(f"  Visemes used: {used}")
        sentences.append({"text": text, "audio_b64": audio_b64, "timeline": timeline})

    print(f"\nWriting demo to {out_path}...")
    write_demo_html(sentences, svgs, out_path)

    import subprocess
    subprocess.run(["open", str(out_path)], check=False)
    print("Done.")


if __name__ == "__main__":
    main()
