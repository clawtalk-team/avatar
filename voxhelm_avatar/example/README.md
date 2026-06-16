# Voxhelm Avatar Example

Demo app showing the `VoxhelmAvatar` widget with audio-driven lip-sync and idle blink animation.

## Running

```bash
cd voxhelm_avatar/example
flutter pub get
flutter run -d macos    # or -d chrome, -d ios, etc.
```

## What it does

- Loads 15 SVG viseme frames for the `young_woman` character from bundled assets
- Loads a pre-built phoneme timeline (`assets/data/timeline.json`)
- Plays audio via `audioplayers` and drives the avatar with `VisemeController.tick()`
- Shows a viseme badge tracking the current mouth shape
- Blink animation runs independently on a random timer

## Assets

SVG heads are generated with the Voxhelm CLI:

```bash
voxhelm generate --preset young_woman
```

Audio and timeline are generated with:

```bash
voxhelm speak --head young_woman --text "Hello, how are you today?"
```

The example bundles heads for all 6 presets plus Flash Image photoreal stills.
