# ClaWTalk SVG Avatar — Flutter Integration Guide

## Overview

The avatar system renders a talking cartoon face by switching between 15 pre-generated SVG frames
(one per viseme) in sync with a phoneme timeline derived from TTS audio.
This document covers what to add to the Flutter app and what changes are needed in the
voice gateway to carry phoneme timestamps downstream.

---

## Package structure

```
photo-generation/flutter_package/
  clawtalk_avatar/
    lib/
      clawtalk_avatar.dart          # barrel export
      src/
        avatar_widget.dart          # main widget
        viseme_controller.dart      # drives frame switching from timeline
        blink_controller.dart       # idle eye-blink timer
        models/
          viseme_set.dart           # 15 SVG strings + metadata
          phoneme_event.dart        # {t: double, viseme: String}
    pubspec.yaml
```

The package exposes a single `ClaWTalkAvatar` widget that accepts:
- A `VisemeSet` (loaded from asset bundle or fetched from API)
- A `Stream<PhonemeEvent>` that drives lip-sync
- Optional size, border-radius, idle animation settings

---

## 1 — Adding the avatar widget to CallScreen

`CallScreen` (`/lib/screens/call_screen.dart`) is where audio plays back. The avatar replaces
or sits alongside the existing `AgentAudioVisualizer`.

### pubspec.yaml additions

```yaml
dependencies:
  flutter_svg: ^2.0.10+1     # renders SVG strings as widgets
  clawtalk_avatar:
    path: ../../photo-generation/flutter_package/clawtalk_avatar
```

### Minimal integration

```dart
// In call_screen.dart
import 'package:clawtalk_avatar/clawtalk_avatar.dart';

// Load the viseme set for the active agent (fetched once, cached)
final visemeSet = await VisemeSet.fromAssetBundle('assets/heads/agent_name');
// or: VisemeSet.fromApi('https://your-api/heads/agent_name/svgs')

// In build():
ClaWTalkAvatar(
  visemeSet: visemeSet,
  events: ref.watch(callProvider).phonemeStream, // see section 3
  size: 200,
)
```

### State management (Riverpod)

Add `phonemeStream` to `CallState`:

```dart
// call_state.dart
final Stream<PhonemeEvent> phonemeStream;
```

The stream is fed by the voice gateway over the existing WebSocket connection
(see section 3 for gateway changes).

---

## 2 — Bundling avatar assets

SVG assets can be bundled at build time or fetched at runtime.

### Bundle at build time

```yaml
# pubspec.yaml
flutter:
  assets:
    - assets/heads/young_woman/    # contains sil.svg, PP.svg, aa.svg … (15 files)
    - assets/heads/older_man/
```

```dart
// Load from bundle
final set = await VisemeSet.fromAssetBundle('assets/heads/young_woman');
```

### Fetch at runtime (recommended for dynamic agent heads)

```dart
// On agent selection, fetch from your API or CDN
final set = await VisemeSet.fromUrl('${config.avatarBaseUrl}/heads/${agent.headId}');
// Cache with flutter_cache_manager or simple in-memory map
```

Runtime fetch is better when agents have distinct generated heads; avoids shipping
large asset bundles for every possible character.

---

## 3 — Voice gateway changes required

The voice gateway (`../voice-gateway`) currently streams only raw PCM audio with no
word or phoneme timing data. Two changes are needed.

### 3a — Add ElevenLabs TTS provider (preferred path)

ElevenLabs returns character-level alignment alongside audio. Their WebSocket endpoint
delivers `normalizedAlignment` objects in each chunk:

```json
{
  "audio": "<base64-mp3-chunk>",
  "normalizedAlignment": {
    "chars": ["H","e","l","l","o"],
    "charStartTimesMs": [0, 68, 124, 165, 210],
    "charDurationsMs":  [68, 56, 41, 45, 180]
  }
}
```

**Gateway changes** (`internal/tts/elevenlabs.go`, new file):

1. Connect to `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`
   with `xi-api-key` header and `output_format=pcm_24000`.
2. Accumulate `normalizedAlignment` chunks into a running character→time table.
3. Map characters → words → phonemes using the same CMU dict the Python demo uses
   (or a server-side lookup table).
4. Emit `PhonemeTimeline` messages on the downstream WebSocket alongside audio frames.

Env var: `TTS_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

**Cost**: ElevenLabs is ~$0.30/1k characters (Turbo v2.5). Deepgram Aura-2 is ~$0.015/1k chars.
For production, evaluate latency vs cost; ElevenLabs first-chunk latency is ~300ms.

### 3b — Keep Deepgram + add post-hoc STT alignment (fallback / no-cost path)

When ElevenLabs is unavailable, keep the existing Deepgram TTS pipeline and run
Deepgram STT on the PCM output after synthesis to recover word timestamps:

1. Buffer the full TTS audio (already done for metrics).
2. POST to `https://api.deepgram.com/v1/listen?model=nova-3&timestamps=true`.
3. Map words → CMU phonemes, distribute evenly within each word's `[start, end]` window.
4. Send the resulting timeline as a `phoneme_timeline` WebSocket message before the
   first audio frame.

This adds ~300–500ms of latency before audio starts. Acceptable for demo; not for
production < 500ms TTFA targets. Toggle with `TTS_ALIGNMENT=stt_passthrough`.

### 3c — New WebSocket message type

Add to the existing message protocol (e.g. `websocket_message.dart` model):

```json
{
  "type": "phoneme_timeline",
  "data": {
    "text": "Hello world",
    "events": [
      {"t": 0.000, "v": "sil",  "ph": "silence"},
      {"t": 0.050, "v": "E",    "ph": "HH"},
      {"t": 0.120, "v": "aa",   "ph": "EH"},
      ...
    ]
  }
}
```

`t` is seconds from start of audio playback. `v` is viseme name (matches SVG filenames).
`ph` is the raw phoneme string (for debugging).

### 3d — Flutter side: consuming the timeline

```dart
// In ws_pcm_transport.dart, add to message handler:
case 'phoneme_timeline':
  final events = (msg.data['events'] as List)
      .map((e) => PhonemeEvent(t: e['t'], viseme: e['v']))
      .toList();
  _phonemeController.add(PhonemeTimeline(events));
  break;
```

`VisemeController` in the avatar package subscribes to `PhonemeTimeline`, starts an
animation loop keyed to the AudioContext/PCM playback position, and drives frame
switching at each phoneme boundary.

---

## 4 — Rendering SVGs in Flutter

`flutter_svg` renders SVG strings as widgets. The avatar widget cycles through them:

```dart
// avatar_widget.dart (simplified)
class ClaWTalkAvatar extends StatefulWidget { ... }

class _ClaWTalkAvatarState extends State<ClaWTalkAvatar> {
  String _currentViseme = 'sil';

  @override
  void initState() {
    super.initState();
    widget.events.listen(_onEvent);
    _startBlink();
  }

  void _onEvent(PhonemeEvent e) {
    setState(() => _currentViseme = e.viseme);
  }

  @override
  Widget build(BuildContext context) {
    final svg = widget.visemeSet.svgs[_currentViseme] ?? widget.visemeSet.svgs['sil']!;
    return Stack(children: [
      SvgPicture.string(svg, width: widget.size, height: widget.size),
      _BlinkOverlay(size: widget.size),  // eye-blink layer
    ]);
  }
}
```

**Performance**: `SvgPicture.string` parses SVG on each frame switch. Pre-parse with
`SvgPicture.string(...).createRenderObject(context)` or cache as `DrawableRoot`
to avoid per-switch parse cost. At 15 visemes this is a one-time 15-parse cache.

---

## 5 — Blink layer

The blink overlay is a `CustomPainter` that draws two skin-coloured ellipses over the
eye positions, animating `ry` from 0→28→0 on a random 4–9s timer:

```dart
// blink_controller.dart
class BlinkController extends ChangeNotifier {
  double eyeRy = 0;
  Timer? _timer;

  void start() => _scheduleNext();

  void _scheduleNext() {
    final delay = Duration(milliseconds: 4000 + Random().nextInt(5000));
    _timer = Timer(delay, _doBlink);
  }

  void _doBlink() {
    // 10 steps × 20ms = 200ms blink
    const steps = [0, 7, 14, 21, 28, 28, 21, 14, 7, 0];
    for (var i = 0; i < steps.length; i++) {
      Future.delayed(Duration(milliseconds: i * 20), () {
        eyeRy = steps[i].toDouble();
        notifyListeners();
      });
    }
    Future.delayed(const Duration(milliseconds: 200), _scheduleNext);
  }
}
```

The eye positions (cx=210/302, cy=240, rx=30 in 512×512 SVG viewBox) are constants
from the character generation prompt. If the prompt changes significantly, re-calibrate
these values against a generated `sil.svg` sample.

---

## 6 — Suggested call_screen.dart diff

```dart
// Before (audio visualizer only):
AgentAudioVisualizer(height: 80)

// After (avatar + visualizer):
Column(children: [
  ClaWTalkAvatar(
    visemeSet: ref.watch(agentHeadProvider(agent.id)),
    events: ref.watch(callProvider).phonemeStream,
    size: 220,
    borderRadius: 16,
  ),
  const SizedBox(height: 16),
  AgentAudioVisualizer(height: 60),
])
```

Add `agentHeadProvider` as a `FutureProvider.family` that fetches and caches the
`VisemeSet` for a given agent ID from your API or asset bundle.

---

## Summary of work required

| Area | Work | Effort |
|------|------|--------|
| `clawtalk_avatar` Flutter package | Widget + VisemeController + BlinkController | ~1 day |
| Voice gateway: ElevenLabs TTS | New `elevenlabs.go` TTS client with alignment | ~1 day |
| Voice gateway: message protocol | Add `phoneme_timeline` message type + publisher | ~0.5 day |
| Flutter app: consume timeline | `ws_pcm_transport.dart` + Riverpod plumbing | ~0.5 day |
| Asset loading / caching | `VisemeSet.fromUrl` + agent head API endpoint | ~0.5 day |
| Testing & calibration | Blink positions, viseme timing, speed | ~1 day |

**Total: ~4.5 days** for a production-ready integration.
For a quick demo with bundled assets and Deepgram STT fallback: ~2 days.
