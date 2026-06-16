import 'dart:convert';
import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;

/// The 15 OVR viseme keys.
const kAllVisemes = [
  'sil', 'PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS',
  'nn', 'RR', 'aa', 'E', 'I', 'O', 'U',
];

/// A set of 15 SVG strings (one per viseme) representing a character's face.
class VisemeSet {
  /// Map of viseme key → SVG string content.
  final Map<String, String> svgs;

  const VisemeSet(this.svgs);

  /// Get the SVG for a viseme, falling back to 'sil' if not found.
  String operator [](String viseme) => svgs[viseme] ?? svgs['sil'] ?? '';

  /// Whether all 15 visemes are present.
  bool get isComplete => svgs.length >= 15;

  /// Number of loaded visemes.
  int get count => svgs.length;

  /// Create from a raw map of viseme key → SVG string.
  factory VisemeSet.fromMap(Map<String, String> svgMap) => VisemeSet(svgMap);

  /// Load from Flutter asset bundle.
  ///
  /// Expects a directory like `assets/heads/young_woman/` containing
  /// `sil.svg`, `PP.svg`, `FF.svg`, etc.
  static Future<VisemeSet> fromAssetBundle(
    BuildContext context,
    String assetPath,
  ) async {
    final bundle = DefaultAssetBundle.of(context);
    final svgs = <String, String>{};

    for (final v in kAllVisemes) {
      try {
        final content = await bundle.loadString('$assetPath/$v.svg');
        svgs[v] = content;
      } catch (_) {
        // SVG not found — skip
      }
    }

    return VisemeSet(svgs);
  }

  /// Fetch from a remote URL that returns a JSON map of {viseme: svgString}.
  ///
  /// This is compatible with the Voxhelm server's `GET /api/head/{name}/svgs`.
  static Future<VisemeSet> fromUrl(String url) async {
    final response = await http.get(Uri.parse(url));
    if (response.statusCode != 200) {
      throw Exception('Failed to load viseme set from $url: ${response.statusCode}');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final svgs = data.map((k, v) => MapEntry(k, v as String));
    return VisemeSet(svgs);
  }

  /// Fetch from a base URL that serves individual SVG files.
  ///
  /// E.g., `fromBaseUrl('https://cdn.example.com/heads/young_woman')`
  /// will fetch `sil.svg`, `PP.svg`, etc.
  static Future<VisemeSet> fromBaseUrl(String baseUrl) async {
    final svgs = <String, String>{};
    final base = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';

    for (final v in kAllVisemes) {
      try {
        final response = await http.get(Uri.parse('$base$v.svg'));
        if (response.statusCode == 200) {
          svgs[v] = response.body;
        }
      } catch (_) {
        // Skip failed fetches
      }
    }

    return VisemeSet(svgs);
  }
}
