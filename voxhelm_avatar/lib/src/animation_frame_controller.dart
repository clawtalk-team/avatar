import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

import 'animation_mode_controller.dart';

/// Cycles through pre-rendered animation frame URLs at a fixed frame rate.
///
/// Each animation mode (idle, listening, thinking) has a sequence of PNG URLs
/// loaded from a CDN. The controller cycles through frames using a [Ticker]
/// and notifies listeners on each frame change.
///
/// In [AnimationMode.speaking] mode, the controller pauses — viseme-driven
/// frame swapping takes over instead.
///
/// ```dart
/// final ctrl = AnimationFrameController(vsync: this, fps: 8);
/// ctrl.loadMode(AnimationMode.idle, [
///   'https://cdn.example.com/heads/bot/anim/idle_001.png',
///   'https://cdn.example.com/heads/bot/anim/idle_002.png',
///   // ...
/// ]);
/// ctrl.mode = AnimationMode.idle;
/// ctrl.start();
/// ```
class AnimationFrameController extends ChangeNotifier {
  AnimationFrameController({
    required TickerProvider vsync,
    this.fps = 8,
  }) {
    _ticker = vsync.createTicker(_onTick);
    _frameDuration = Duration(milliseconds: (1000 / fps).round());
  }

  /// Frames per second for animation playback.
  final int fps;

  /// Frame URLs per animation mode.
  final Map<AnimationMode, List<String>> _frames = {};

  Ticker? _ticker;
  late final Duration _frameDuration;
  Duration _elapsed = Duration.zero;
  Duration _lastFrameTime = Duration.zero;
  AnimationMode _mode = AnimationMode.idle;
  int _frameIndex = 0;
  bool _running = false;

  /// The current animation mode.
  AnimationMode get mode => _mode;

  /// Set the animation mode. Resets frame index to 0.
  set mode(AnimationMode value) {
    if (_mode == value) return;
    _mode = value;
    _frameIndex = 0;
    _lastFrameTime = _elapsed;
    notifyListeners();
  }

  /// Whether the animation loop is running.
  bool get isRunning => _running;

  /// The current frame URL, or null if no frames are loaded for the mode.
  String? get currentFrameUrl {
    if (_mode == AnimationMode.speaking) return null;
    final modeFrames = _frames[_mode];
    if (modeFrames == null || modeFrames.isEmpty) return null;
    return modeFrames[_frameIndex % modeFrames.length];
  }

  /// The current frame index.
  int get frameIndex => _frameIndex;

  /// Whether frames are loaded for the given mode.
  bool hasFrames(AnimationMode mode) {
    final f = _frames[mode];
    return f != null && f.isNotEmpty;
  }

  /// Whether frames are loaded for any non-speaking mode.
  bool get hasAnyFrames =>
      hasFrames(AnimationMode.idle) ||
      hasFrames(AnimationMode.listening) ||
      hasFrames(AnimationMode.thinking);

  /// Load frame URLs for an animation mode.
  void loadMode(AnimationMode mode, List<String> urls) {
    _frames[mode] = List.unmodifiable(urls);
  }

  /// Build frame URLs from a CDN base URL for a specific mode.
  ///
  /// Generates URLs like `{baseUrl}/anim/{mode}_{001..frameCount}.png`.
  void loadModeFromCdn(
    AnimationMode mode,
    String baseUrl, {
    int frameCount = 32,
    String ext = 'png',
  }) {
    final base = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
    final modeName = mode.name; // idle, listening, thinking
    final urls = List.generate(frameCount, (i) {
      final num = (i + 1).toString().padLeft(3, '0');
      return '${base}anim/${modeName}_$num.$ext';
    });
    loadMode(mode, urls);
  }

  /// Load all three animation modes from a CDN base URL.
  void loadAllFromCdn(String baseUrl, {int frameCount = 32, String ext = 'png'}) {
    for (final mode in [
      AnimationMode.idle,
      AnimationMode.listening,
      AnimationMode.thinking,
    ]) {
      loadModeFromCdn(mode, baseUrl, frameCount: frameCount, ext: ext);
    }
  }

  /// Start the animation loop.
  void start() {
    if (_running) return;
    _running = true;
    _elapsed = Duration.zero;
    _lastFrameTime = Duration.zero;
    _ticker?.start();
  }

  /// Stop the animation loop and reset.
  void stop() {
    _running = false;
    _ticker?.stop();
    _elapsed = Duration.zero;
    _lastFrameTime = Duration.zero;
    _frameIndex = 0;
    notifyListeners();
  }

  void _onTick(Duration elapsed) {
    _elapsed = elapsed;

    // Don't advance frames during speaking mode.
    if (_mode == AnimationMode.speaking) return;

    final modeFrames = _frames[_mode];
    if (modeFrames == null || modeFrames.isEmpty) return;

    // Advance frame at the configured FPS.
    if (elapsed - _lastFrameTime >= _frameDuration) {
      _lastFrameTime = elapsed;
      _frameIndex = (_frameIndex + 1) % modeFrames.length;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _ticker?.dispose();
    super.dispose();
  }
}
