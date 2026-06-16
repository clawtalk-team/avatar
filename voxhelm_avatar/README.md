# voxhelm_avatar

SVG talking avatar widget for Flutter with viseme-driven lip-sync and idle blink animation.

## Quick Start

```dart
import 'package:voxhelm_avatar/voxhelm_avatar.dart';

// 1. Load SVG viseme set (15 frames per character)
final visemeSet = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');
// Or from API: VisemeSet.fromUrl('http://localhost:7432/api/head/young_woman/svgs')
// Or from map: VisemeSet.fromMap({'sil': '<svg>...</svg>', 'PP': '<svg>...</svg>', ...})

// 2. Create controllers
final visemeCtrl = VisemeController();
final blinkCtrl = BlinkController()..start();

// 3. Set a timeline (from your audio pipeline)
visemeCtrl.setTimeline(PhonemeTimeline.fromJson(timelineData));

// 4. Build the widget
VoxhelmAvatar(
  visemeSet: visemeSet,
  controller: visemeCtrl,
  blinkController: blinkCtrl,
  size: 200,
  borderRadius: BorderRadius.circular(16),
)

// 5. Drive from audio position (call this each frame)
visemeCtrl.tick(audioPlayer.position.inMilliseconds / 1000.0);
```

## Architecture

The package has no audio dependency. Your app owns audio playback and feeds
the current position to `VisemeController.tick()`.

```
Your App                          voxhelm_avatar
┌─────────────────┐              ┌──────────────────────┐
│ Audio Player     │──position──▶│ VisemeController      │
│ WebSocket stream │──events───▶│   .tick(seconds)      │
│                  │             │   .bindStream(stream) │
└─────────────────┘              │   .currentViseme ─────┼──▶ VoxhelmAvatar
                                 ├──────────────────────┤      (SVG switching
                                 │ BlinkController       │       + blink overlay)
                                 │   .start() / .stop()  │
                                 └──────────────────────┘
```

## API Reference

### Models

#### `PhonemeEvent`
A single viseme event in a timeline.

| Field | Type | Description |
|-------|------|-------------|
| `t` | `double` | Time in seconds from audio start |
| `viseme` | `String` | Viseme key (sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, I, O, U) |
| `phoneme` | `String?` | Raw ARPAbet phoneme (debug) |

#### `PhonemeTimeline`
A list of `PhonemeEvent`s with binary-search lookup.

```dart
final timeline = PhonemeTimeline.fromJson(jsonList);
String viseme = timeline.visemeAtTime(1.5); // → "aa"
```

Also supports legacy format: `PhonemeTimeline.fromLegacy(frames)` for
`{viseme, start_ms, end_ms}` format.

#### `VisemeSet`
15 SVG strings keyed by viseme name.

```dart
// From Flutter assets
final set = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');

// From Voxhelm server API
final set = await VisemeSet.fromUrl('http://localhost:7432/api/head/young_woman/svgs');

// From individual SVG files on a CDN
final set = await VisemeSet.fromBaseUrl('https://cdn.example.com/heads/young_woman');

// From raw map
final set = VisemeSet.fromMap({'sil': '<svg>...</svg>', ...});

set['aa']      // SVG string for the "aa" viseme
set.isComplete // true if all 15 visemes loaded
set.count      // number of loaded visemes
```

### Controllers

#### `VisemeController`
Drives viseme frame switching. Two modes:

**Timeline mode** (pre-built timeline, ticked by audio position):
```dart
final ctrl = VisemeController();
ctrl.setTimeline(timeline);

// In your audio callback:
ctrl.tick(audioPositionSeconds);
```

**Stream mode** (real-time events from WebSocket):
```dart
ctrl.bindStream(phonemeEventStream);
```

Read the current viseme: `ctrl.currentViseme` (String).
Listen for changes: `ctrl.addListener(callback)`.

#### `BlinkController`
Idle eye-blink animation. 200ms blink cycle on a random 4-9 second interval.

```dart
final blink = BlinkController()..start();
blink.eyeClosedness // 0.0 (open) to 1.0 (closed)
blink.stop();
```

### Widget

#### `VoxhelmAvatar`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `visemeSet` | `VisemeSet` | required | SVG frames |
| `controller` | `VisemeController` | required | Viseme driver |
| `blinkController` | `BlinkController?` | null | Blink animation |
| `size` | `double` | 200 | Width and height |
| `borderRadius` | `BorderRadius?` | null | Clip radius |
| `backgroundColor` | `Color` | #1A1A1A | Background |
| `leftEyeCenter` | `Offset` | (210, 240) | Left eye in 512x512 SVG space |
| `rightEyeCenter` | `Offset` | (302, 240) | Right eye in 512x512 SVG space |
| `eyeRadiusX` | `double` | 30 | Eye horizontal radius |
| `eyeRadiusY` | `double` | 28 | Eye vertical radius (max when closed) |
| `eyelidColor` | `Color` | #F5C4A1 | Eyelid fill (match skin tone) |

## Timeline Format

The timeline JSON expected by `PhonemeTimeline.fromJson()`:

```json
[
  {"t": 0.000, "v": "sil", "ph": "SIL"},
  {"t": 0.050, "v": "E",   "ph": "HH"},
  {"t": 0.120, "v": "aa",  "ph": "AH"},
  {"t": 0.450, "v": "sil", "ph": "SIL"}
]
```

This is the exact format produced by the `voxhelm speak` CLI command and
the Voxhelm server's `POST /api/speak` endpoint.

## Generating Assets

Use the [Voxhelm CLI](../docs/cli_usage.md) to generate SVG heads and
audio timelines:

```bash
pip install -e .
voxhelm generate --preset young_woman
voxhelm speak --head young_woman --text "Hello world"
voxhelm validate --head young_woman
```
