import 'dart:async';
import 'package:flutter/foundation.dart';
import 'models/phoneme_event.dart';

/// Controls which viseme frame is displayed.
///
/// Supports two modes:
/// - **Timeline mode**: Set a [PhonemeTimeline] upfront, then call [tick] each
///   frame with the current audio position.
/// - **Stream mode**: Bind a [Stream<PhonemeEvent>] for real-time updates
///   (e.g., from a WebSocket).
class VisemeController extends ChangeNotifier {
  String _currentViseme = 'sil';
  PhonemeTimeline? _timeline;
  StreamSubscription<PhonemeEvent>? _streamSub;

  /// The currently active viseme key.
  String get currentViseme => _currentViseme;

  /// Set a pre-built timeline. Call [tick] each frame to advance.
  void setTimeline(PhonemeTimeline timeline) {
    _streamSub?.cancel();
    _streamSub = null;
    _timeline = timeline;
    _currentViseme = 'sil';
    notifyListeners();
  }

  /// Bind a stream of real-time viseme events (e.g., from WebSocket).
  void bindStream(Stream<PhonemeEvent> stream) {
    _timeline = null;
    _streamSub?.cancel();
    _streamSub = stream.listen((event) {
      if (_currentViseme != event.viseme) {
        _currentViseme = event.viseme;
        notifyListeners();
      }
    });
  }

  /// Advance the timeline to the given audio position (in seconds).
  ///
  /// Call this from your audio player's position callback or a Ticker.
  void tick(double audioPositionSeconds) {
    if (_timeline == null) return;
    final v = _timeline!.visemeAtTime(audioPositionSeconds);
    if (v != _currentViseme) {
      _currentViseme = v;
      notifyListeners();
    }
  }

  /// Reset to silent.
  void reset() {
    _currentViseme = 'sil';
    notifyListeners();
  }

  @override
  void dispose() {
    _streamSub?.cancel();
    super.dispose();
  }
}
