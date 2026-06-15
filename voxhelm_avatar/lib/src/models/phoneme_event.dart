/// A single phoneme/viseme event in a timeline.
class PhonemeEvent {
  /// Time in seconds from the start of audio.
  final double t;

  /// Viseme key — one of the 15 OVR visemes (sil, PP, FF, TH, DD, kk, CH, SS,
  /// nn, RR, aa, E, I, O, U).
  final String viseme;

  /// Raw phoneme string (for debugging). Optional.
  final String? phoneme;

  const PhonemeEvent({required this.t, required this.viseme, this.phoneme});

  factory PhonemeEvent.fromJson(Map<String, dynamic> json) {
    return PhonemeEvent(
      t: (json['t'] as num).toDouble(),
      viseme: json['v'] as String,
      phoneme: json['ph'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        't': t,
        'v': viseme,
        if (phoneme != null) 'ph': phoneme,
      };
}

/// A complete phoneme timeline for an audio clip.
class PhonemeTimeline {
  final List<PhonemeEvent> events;

  const PhonemeTimeline(this.events);

  factory PhonemeTimeline.fromJson(List<dynamic> json) {
    return PhonemeTimeline(
      json.map((e) => PhonemeEvent.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }

  /// Look up the viseme at a given time (seconds) using binary search.
  String visemeAtTime(double seconds) {
    if (events.isEmpty) return 'sil';

    // Binary search for the last event with t <= seconds
    int lo = 0, hi = events.length - 1;
    int result = 0;
    while (lo <= hi) {
      final mid = (lo + hi) ~/ 2;
      if (events[mid].t <= seconds) {
        result = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return events[result].viseme;
  }

  /// Create from the legacy format used by avatar_demo ({viseme, start_ms, end_ms}).
  factory PhonemeTimeline.fromLegacy(List<Map<String, dynamic>> frames) {
    final events = frames.map((f) {
      return PhonemeEvent(
        t: (f['start_ms'] as int) / 1000.0,
        viseme: f['viseme'] as String,
      );
    }).toList();
    return PhonemeTimeline(events);
  }

  List<dynamic> toJson() => events.map((e) => e.toJson()).toList();
}
