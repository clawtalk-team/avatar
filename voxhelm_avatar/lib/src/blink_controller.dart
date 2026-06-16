import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';

/// Controls idle eye-blink animation.
///
/// Drives a 200ms blink cycle (10 steps x 20ms) on a random 4-9 second
/// interval, with a 25% chance of a double-blink.
///
/// [eyeClosedness] ranges from 0.0 (fully open) to 1.0 (fully closed).
class BlinkController extends ChangeNotifier {
  static const _blinkSteps = [0, 7, 14, 21, 28, 28, 21, 14, 7, 0];
  static const _stepMs = 20;
  static const _maxRy = 28.0;

  final _rng = Random();

  double _eyeClosedness = 0.0;
  Timer? _scheduleTimer;
  bool _running = false;
  bool _disposed = false;

  /// Current eye closedness: 0.0 = open, 1.0 = closed.
  double get eyeClosedness => _eyeClosedness;

  /// Start the blink loop.
  void start() {
    if (_running) return;
    _running = true;
    _scheduleNext();
  }

  /// Stop the blink loop and reset to open.
  void stop() {
    _running = false;
    _scheduleTimer?.cancel();
    _scheduleTimer = null;
    _eyeClosedness = 0.0;
    if (!_disposed) notifyListeners();
  }

  void _scheduleNext() {
    if (!_running || _disposed) return;
    final delayMs = 4000 + _rng.nextInt(5000);
    _scheduleTimer = Timer(Duration(milliseconds: delayMs), _doBlink);
  }

  void _doBlink() {
    if (!_running || _disposed) return;
    _runBlinkSequence(() {
      if (!_running || _disposed) return;
      // 25% chance of double-blink
      if (_rng.nextDouble() < 0.25) {
        Timer(const Duration(milliseconds: 250), () {
          if (!_running || _disposed) return;
          _runBlinkSequence(_scheduleNext);
        });
      } else {
        _scheduleNext();
      }
    });
  }

  void _runBlinkSequence(VoidCallback onDone) {
    for (var i = 0; i < _blinkSteps.length; i++) {
      Timer(Duration(milliseconds: i * _stepMs), () {
        if (_disposed) return;
        _eyeClosedness = _blinkSteps[i] / _maxRy;
        notifyListeners();
      });
    }
    Timer(Duration(milliseconds: _blinkSteps.length * _stepMs), onDone);
  }

  @override
  void dispose() {
    _disposed = true;
    _scheduleTimer?.cancel();
    super.dispose();
  }
}
