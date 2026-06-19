import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// Avatar animation modes.
enum AnimationMode {
  /// Gentle breathing, subtle micro-movements.
  idle,

  /// Attentive: slight lean forward, small nods.
  listening,

  /// Contemplative: eyes drift, brow furrow/raise.
  thinking,

  /// Mouth driven by viseme controller — transforms are neutral.
  speaking,
}

/// A single transform for one SVG group.
class GroupTransform {
  final double tx;
  final double ty;
  final double r;
  final double sx;
  final double sy;

  const GroupTransform({
    this.tx = 0,
    this.ty = 0,
    this.r = 0,
    this.sx = 1.0,
    this.sy = 1.0,
  });

  static const neutral = GroupTransform();

  /// Linearly interpolate between two transforms.
  static GroupTransform lerp(GroupTransform a, GroupTransform b, double t) {
    return GroupTransform(
      tx: a.tx + (b.tx - a.tx) * t,
      ty: a.ty + (b.ty - a.ty) * t,
      r: a.r + (b.r - a.r) * t,
      sx: a.sx + (b.sx - a.sx) * t,
      sy: a.sy + (b.sy - a.sy) * t,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GroupTransform &&
          tx == other.tx &&
          ty == other.ty &&
          r == other.r &&
          sx == other.sx &&
          sy == other.sy;

  @override
  int get hashCode => Object.hash(tx, ty, r, sx, sy);
}

/// A keyframe in an animation sequence.
class AnimationKeyframe {
  /// Position in the loop, 0.0 to 1.0.
  final double t;

  /// Transform per SVG group.
  final Map<String, GroupTransform> groups;

  const AnimationKeyframe({required this.t, required this.groups});
}

/// A looped animation sequence.
class AnimationSequence {
  final AnimationMode mode;
  final int durationMs;
  final List<AnimationKeyframe> keyframes;

  const AnimationSequence({
    required this.mode,
    required this.durationMs,
    required this.keyframes,
  });
}

/// Smoothstep easing: 3t^2 - 2t^3
double _smoothstep(double t) => t * t * (3.0 - 2.0 * t);

// ── Built-in animation sequences ────────────────────────────────────────────

const _n = GroupTransform.neutral;

const _idleSequence = AnimationSequence(
  mode: AnimationMode.idle,
  durationMs: 4000,
  keyframes: [
    AnimationKeyframe(t: 0.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
    AnimationKeyframe(t: 0.15, groups: {
      'head': GroupTransform(tx: 2, ty: -6, r: 1.2),
      'eyes': GroupTransform(tx: 4, ty: -2),
      'brows': GroupTransform(ty: -3),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.35, groups: {
      'head': GroupTransform(tx: 5, ty: -10, r: 2.0),
      'eyes': GroupTransform(tx: 6, ty: -3),
      'brows': GroupTransform(ty: -4),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.50, groups: {
      'head': GroupTransform(tx: 2, ty: -4, r: 0.8),
      'eyes': GroupTransform(tx: 2, ty: -1),
      'brows': GroupTransform(ty: -2),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.70, groups: {
      'head': GroupTransform(tx: -4, ty: 2, r: -1.5),
      'eyes': GroupTransform(tx: -5, ty: 2),
      'brows': GroupTransform(ty: 1),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.85, groups: {
      'head': GroupTransform(tx: -2, ty: 1, r: -0.5),
      'eyes': GroupTransform(tx: -2),
      'brows': _n,
      'mouth': _n,
    }),
    AnimationKeyframe(t: 1.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
  ],
);

const _listeningSequence = AnimationSequence(
  mode: AnimationMode.listening,
  durationMs: 3000,
  keyframes: [
    AnimationKeyframe(t: 0.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
    AnimationKeyframe(t: 0.10, groups: {
      'head': GroupTransform(ty: -8, r: -1.5, sx: 1.005, sy: 1.005),
      'eyes': GroupTransform(sx: 1.02, sy: 1.04),
      'brows': GroupTransform(ty: -5),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.25, groups: {
      'head': GroupTransform(ty: 8, r: -3.0, sx: 1.005, sy: 1.005),
      'eyes': GroupTransform(ty: 3, sx: 1.02, sy: 1.04),
      'brows': GroupTransform(ty: -3),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.35, groups: {
      'head': GroupTransform(ty: -6, r: -1.0, sx: 1.005, sy: 1.005),
      'eyes': GroupTransform(tx: 2, ty: -2, sx: 1.02, sy: 1.04),
      'brows': GroupTransform(ty: -4),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.55, groups: {
      'head': GroupTransform(tx: 7, ty: -4, r: 4.0, sx: 1.005, sy: 1.005),
      'eyes': GroupTransform(tx: -3, sx: 1.02, sy: 1.04),
      'brows': GroupTransform(ty: -3),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.70, groups: {
      'head': GroupTransform(tx: 4, ty: 4, r: 2.5, sx: 1.003, sy: 1.003),
      'eyes': GroupTransform(tx: -2, ty: 2, sx: 1.01, sy: 1.02),
      'brows': GroupTransform(ty: -2),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.85, groups: {
      'head': GroupTransform(tx: 2, ty: -2, r: 1.0),
      'eyes': GroupTransform(sx: 1.005, sy: 1.01),
      'brows': GroupTransform(ty: -1),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 1.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
  ],
);

const _thinkingSequence = AnimationSequence(
  mode: AnimationMode.thinking,
  durationMs: 5000,
  keyframes: [
    AnimationKeyframe(t: 0.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
    AnimationKeyframe(t: 0.10, groups: {
      'head': GroupTransform(tx: 3, ty: -3, r: 2.0),
      'eyes': GroupTransform(tx: 12, ty: -10),
      'brows': GroupTransform(ty: -2, r: -1.5),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.25, groups: {
      'head': GroupTransform(tx: 8, ty: -6, r: 5.0),
      'eyes': GroupTransform(tx: 18, ty: -15, sy: 0.92),
      'brows': GroupTransform(ty: 5, r: -3.0, sy: 0.9),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.40, groups: {
      'head': GroupTransform(tx: 10, ty: -4, r: 6.0),
      'eyes': GroupTransform(tx: 15, ty: -14, sy: 0.92),
      'brows': GroupTransform(ty: 6, r: -2.5, sy: 0.88),
      'mouth': GroupTransform(tx: 2, sx: 0.95, sy: 0.92),
    }),
    AnimationKeyframe(t: 0.55, groups: {
      'head': GroupTransform(tx: -5, ty: -3, r: -3.0),
      'eyes': GroupTransform(tx: -12, ty: -8, sy: 0.95),
      'brows': GroupTransform(ty: 4, r: 1.5, sy: 0.92),
      'mouth': GroupTransform(tx: -1, sx: 0.96, sy: 0.94),
    }),
    AnimationKeyframe(t: 0.70, groups: {
      'head': GroupTransform(tx: -3, ty: -6, r: -1.5),
      'eyes': GroupTransform(tx: -4, ty: -4, sx: 1.02, sy: 1.06),
      'brows': GroupTransform(ty: -8),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 0.85, groups: {
      'head': GroupTransform(tx: -1, ty: -2, r: -0.5),
      'eyes': GroupTransform(tx: -2, ty: -2),
      'brows': GroupTransform(ty: -3),
      'mouth': _n,
    }),
    AnimationKeyframe(t: 1.0, groups: {
      'head': _n, 'eyes': _n, 'brows': _n, 'mouth': _n,
    }),
  ],
);

/// Map of built-in animation sequences.
const builtInAnimations = <AnimationMode, AnimationSequence>{
  AnimationMode.idle: _idleSequence,
  AnimationMode.listening: _listeningSequence,
  AnimationMode.thinking: _thinkingSequence,
};

/// Drives looped animation transforms for idle/listening/thinking modes.
///
/// Notifies listeners each frame with the current group transforms.
/// In [AnimationMode.speaking] mode, all transforms are neutral (identity)
/// so the viseme controller drives the mouth directly.
///
/// ```dart
/// final animCtrl = AnimationModeController(vsync: this);
/// animCtrl.mode = AnimationMode.idle;
/// animCtrl.start();
/// // ...
/// animCtrl.mode = AnimationMode.listening; // instant switch
/// ```
class AnimationModeController extends ChangeNotifier {
  AnimationMode _mode = AnimationMode.idle;
  Ticker? _ticker;
  Duration _elapsed = Duration.zero;
  bool _running = false;

  /// Current group transforms, updated each tick.
  Map<String, GroupTransform> _currentTransforms = {
    'head': GroupTransform.neutral,
    'eyes': GroupTransform.neutral,
    'brows': GroupTransform.neutral,
    'mouth': GroupTransform.neutral,
  };

  /// Custom animation sequences (overrides built-ins).
  final Map<AnimationMode, AnimationSequence> _customSequences = {};

  /// Create a controller. Provide a [TickerProvider] for frame callbacks.
  AnimationModeController({required TickerProvider vsync}) {
    _ticker = vsync.createTicker(_onTick);
  }

  /// The current animation mode.
  AnimationMode get mode => _mode;

  /// Set the animation mode. Transitions are instant — all sequences share
  /// the same neutral start/end frame.
  set mode(AnimationMode value) {
    if (_mode == value) return;
    _mode = value;
    _elapsed = Duration.zero;
    if (value == AnimationMode.speaking) {
      _currentTransforms = {
        'head': GroupTransform.neutral,
        'eyes': GroupTransform.neutral,
        'brows': GroupTransform.neutral,
        'mouth': GroupTransform.neutral,
      };
      notifyListeners();
    }
  }

  /// Whether the animation loop is running.
  bool get isRunning => _running;

  /// Current transforms for each SVG group.
  Map<String, GroupTransform> get transforms =>
      Map.unmodifiable(_currentTransforms);

  /// Get the transform for a specific group.
  GroupTransform transformFor(String group) =>
      _currentTransforms[group] ?? GroupTransform.neutral;

  /// Register a custom animation sequence.
  void setSequence(AnimationSequence sequence) {
    _customSequences[sequence.mode] = sequence;
  }

  /// Start the animation loop.
  void start() {
    if (_running) return;
    _running = true;
    _elapsed = Duration.zero;
    _ticker?.start();
  }

  /// Stop the animation loop and reset to neutral.
  void stop() {
    _running = false;
    _ticker?.stop();
    _elapsed = Duration.zero;
    _currentTransforms = {
      'head': GroupTransform.neutral,
      'eyes': GroupTransform.neutral,
      'brows': GroupTransform.neutral,
      'mouth': GroupTransform.neutral,
    };
    notifyListeners();
  }

  AnimationSequence? _getSequence() {
    return _customSequences[_mode] ?? builtInAnimations[_mode];
  }

  void _onTick(Duration elapsed) {
    _elapsed = elapsed;

    if (_mode == AnimationMode.speaking) return;

    final seq = _getSequence();
    if (seq == null) return;

    final ms = elapsed.inMicroseconds / 1000.0;
    final tNorm = (ms % seq.durationMs) / seq.durationMs;

    // Find bracketing keyframes
    final kfs = seq.keyframes;
    var prev = kfs.first;
    var nxt = kfs.last;
    for (int i = 0; i < kfs.length - 1; i++) {
      if (tNorm >= kfs[i].t && tNorm <= kfs[i + 1].t) {
        prev = kfs[i];
        nxt = kfs[i + 1];
        break;
      }
    }

    final span = nxt.t - prev.t;
    final localT = span > 0 ? _smoothstep((tNorm - prev.t) / span) : 0.0;

    // Interpolate each group
    final allGroups = <String>{...prev.groups.keys, ...nxt.groups.keys};
    final newTransforms = <String, GroupTransform>{};
    for (final gid in allGroups) {
      final a = prev.groups[gid] ?? GroupTransform.neutral;
      final b = nxt.groups[gid] ?? GroupTransform.neutral;
      newTransforms[gid] = GroupTransform.lerp(a, b, localT);
    }

    _currentTransforms = newTransforms;
    notifyListeners();
  }

  @override
  void dispose() {
    _ticker?.dispose();
    super.dispose();
  }
}
