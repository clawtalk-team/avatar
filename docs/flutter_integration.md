# Voxhelm SVG Avatar — Flutter Integration Guide

## Overview

The avatar system renders a talking cartoon face by switching between 15 pre-generated SVG frames
(one per viseme) in sync with a phoneme timeline derived from TTS audio.
This document covers how to use the `voxhelm_avatar` Flutter package and what changes are
needed in the voice gateway to carry phoneme timestamps downstream.

---

## Package structure

```
voxhelm_avatar/
  lib/
    voxhelm_avatar.dart             # barrel export
    src/
      avatar_widget.dart            # VoxhelmAvatar widget
      viseme_controller.dart        # drives frame switching from timeline or stream
      blink_controller.dart         # idle eye-blink animation
      models/
        viseme_set.dart             # 15 SVG strings + loaders
        phoneme_event.dart          # PhonemeEvent, PhonemeTimeline
  pubspec.yaml
  example/                          # demo app with bundled assets
```

The package exposes a `VoxhelmAvatar` widget that accepts:
- A `VisemeSet` (loaded from asset bundle, URL, or raw map)
- A `VisemeController` that drives lip-sync (timeline or stream mode)
- An optional `BlinkController` for idle eye-blink animation
- Configurable size, border-radius, eye positions, and eyelid colour

The package has **no audio dependency** — the host app owns audio playback and
feeds the current position to `VisemeController.tick()`.

---

## 1 — Adding the avatar widget to CallScreen

`CallScreen` (`/lib/screens/call_screen.dart`) is where audio plays back. The avatar
replaces or sits alongside the existing `AgentAudioVisualizer`.

### pubspec.yaml additions

```yaml
dependencies:
  voxhelm_avatar:
    path: ../avatar/voxhelm_avatar   # or a git/pub dependency
```

(`flutter_svg` is a transitive dependency of `voxhelm_avatar` — no need to add it directly.)

### Minimal integration

```dart
import 'package:voxhelm_avatar/voxhelm_avatar.dart';

// Load the viseme set for the active agent (fetched once, cached)
final visemeSet = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');
// or: VisemeSet.fromUrl('https://your-api/heads/young_woman/svgs')

// Create controllers
final visemeCtrl = VisemeController();
final blinkCtrl = BlinkController()..start();

// Set a timeline (from your phoneme pipeline)
visemeCtrl.setTimeline(timeline);

// In build():
VoxhelmAvatar(
  visemeSet: visemeSet,
  controller: visemeCtrl,
  blinkController: blinkCtrl,
  size: 200,
  borderRadius: BorderRadius.circular(16),
)

// Drive from audio position (in your audio player callback):
visemeCtrl.tick(audioPositionSeconds);
```

### State management (Riverpod)

Add `phonemeTimeline` to `CallState` and drive from position changes:

```dart
// In your audio player callback:
player.onPositionChanged.listen((pos) {
  visemeCtrl.tick(pos.inMilliseconds / 1000.0);
});
```

For real-time WebSocket-driven visemes (no pre-built timeline):

```dart
visemeCtrl.bindStream(phonemeEventStream);
```

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
// Load from bundle (requires BuildContext)
final set = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');
```

### Fetch at runtime (recommended for dynamic agent heads)

```dart
// From Voxhelm server API (returns JSON map)
final set = await VisemeSet.fromUrl('${config.avatarBaseUrl}/api/head/${agent.headId}/svgs');

// Or from individual SVG files on a CDN
final set = await VisemeSet.fromBaseUrl('https://cdn.example.com/heads/${agent.headId}');
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
2. Accumulate `normalizedAlignment` chunks into a running character-to-time table.
3. Map characters to words to phonemes using CMU dict (or a server-side lookup table).
4. Emit `PhonemeTimeline` messages on the downstream WebSocket alongside audio frames.

Env var: `TTS_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

**Cost**: ElevenLabs is ~$0.30/1k characters (Turbo v2.5). Deepgram Aura-2 is ~$0.015/1k chars.
For production, evaluate latency vs cost; ElevenLabs first-chunk latency is ~300ms.

### 3b — Keep Deepgram + add post-hoc STT alignment (fallback / no-cost path)

When ElevenLabs is unavailable, keep the existing Deepgram TTS pipeline and run
Deepgram STT on the PCM output after synthesis to recover word timestamps:

1. Buffer the full TTS audio (already done for metrics).
2. POST to `https://api.deepgram.com/v1/listen?model=nova-3&words=true`.
3. Map words to CMU phonemes, distribute evenly within each word's `[start, end]` window.
4. Send the resulting timeline as a `phoneme_timeline` WebSocket message before the
   first audio frame.

This adds ~300-500ms of latency before audio starts. Acceptable for demo; not for
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
      {"t": 0.120, "v": "aa",   "ph": "EH"}
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
  final timeline = PhonemeTimeline(events);
  visemeController.setTimeline(timeline);
  break;
```

`VisemeController` then needs `tick(audioPositionSeconds)` called each frame by the
host app's audio player position callback.

---

## 4 — Rendering SVGs in Flutter

`flutter_svg` renders SVG strings as widgets. The `VoxhelmAvatar` widget manages this
internally with a pre-parsed cache:

```dart
// avatar_widget.dart (simplified)
class VoxhelmAvatar extends StatefulWidget {
  final VisemeSet visemeSet;
  final VisemeController controller;
  final BlinkController? blinkController;
  final double size;
  final BorderRadius? borderRadius;
  final Color backgroundColor;
  // Eye position config for blink overlay (512x512 SVG space)
  final Offset leftEyeCenter;   // default (210, 240)
  final Offset rightEyeCenter;  // default (302, 240)
  final double eyeRadiusX;      // default 30
  final double eyeRadiusY;      // default 28
  final Color eyelidColor;      // default skin tone
  ...
}
```

Internally, `_buildSvgCache()` pre-parses all 15 SVGs via `SvgPicture.string()` on load.
Frame switching is an instant widget swap — no per-frame parse cost. The cache rebuilds
automatically when `visemeSet` or `size` changes.

---

## 5 — Blink layer

The blink overlay is a `CustomPainter` that draws two skin-coloured ellipses over the
eye positions, driven by `BlinkController`:

```dart
final blinkCtrl = BlinkController()..start();

// BlinkController exposes:
blinkCtrl.eyeClosedness  // 0.0 (open) → 1.0 (closed)
blinkCtrl.start()        // begin blink loop
blinkCtrl.stop()         // stop and reset to open
```

Blink cycle: 10 steps x 20ms = 200ms. Random 4-9s interval between blinks, with a
25% chance of a double-blink.

The eye positions (cx=210/302, cy=240, rx=30 in 512x512 SVG viewBox) are configurable
via the `VoxhelmAvatar` widget's `leftEyeCenter`, `rightEyeCenter`, `eyeRadiusX`,
`eyeRadiusY`, and `eyelidColor` parameters. Calibrate against your character's `sil.svg`.

---

## 6 — Suggested call_screen.dart diff

```dart
// Before (audio visualizer only):
AgentAudioVisualizer(height: 80)

// After (avatar + visualizer):
Column(children: [
  VoxhelmAvatar(
    visemeSet: ref.watch(agentHeadProvider(agent.id)),
    controller: ref.watch(visemeControllerProvider),
    blinkController: ref.watch(blinkControllerProvider),
    size: 220,
    borderRadius: BorderRadius.circular(16),
  ),
  const SizedBox(height: 16),
  AgentAudioVisualizer(height: 60),
])
```

Add `agentHeadProvider` as a `FutureProvider.family` that fetches and caches the
`VisemeSet` for a given agent ID from your API or asset bundle.

---

## Summary of remaining work

The `voxhelm_avatar` Flutter package is implemented and ready to import. The remaining
integration work is on the voice gateway and app plumbing side:

| Area | Work | Effort |
|------|------|--------|
| Voice gateway: ElevenLabs TTS | New `elevenlabs.go` TTS client with alignment | ~1 day |
| Voice gateway: message protocol | Add `phoneme_timeline` message type + publisher | ~0.5 day |
| Flutter app: consume timeline | `ws_pcm_transport.dart` + Riverpod plumbing | ~0.5 day |
| Asset loading / caching | `VisemeSet.fromUrl` + agent head API endpoint | ~0.5 day |
| Testing & calibration | Blink positions, viseme timing, speed | ~1 day |

**Total: ~3.5 days** for a production-ready integration.
For a quick demo with bundled assets and Deepgram STT fallback: ~1.5 days.
