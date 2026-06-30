import 'dart:convert';
import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;

/// The 15 OVR viseme keys.
const kAllVisemes = [
  'sil', 'PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS',
  'nn', 'RR', 'aa', 'E', 'I', 'O', 'U',
];

/// Asset mode: SVG strings or PNG URLs.
enum VisemeMode { svg, png }

/// A set of 15 viseme assets representing a character's face.
///
/// Supports two modes:
/// - [VisemeMode.svg]: assets are raw SVG strings (rendered with flutter_svg)
/// - [VisemeMode.png]: assets are image URLs (rendered with Image.network)
class VisemeSet {
  /// Map of viseme key → asset (SVG string or URL).
  final Map<String, String> assets;

  /// The asset mode.
  final VisemeMode mode;

  const VisemeSet(this.assets, {this.mode = VisemeMode.svg});

  /// Legacy accessor — returns the SVG/URL map.
  Map<String, String> get svgs => assets;

  /// Get the asset for a viseme, falling back to 'sil' if not found.
  String operator [](String viseme) => assets[viseme] ?? assets['sil'] ?? '';

  /// Whether all 15 visemes are present.
  bool get isComplete => assets.length >= 15;

  /// Number of loaded visemes.
  int get count => assets.length;

  /// Whether this is an SVG set.
  bool get isSvg => mode == VisemeMode.svg;

  /// Whether this is a PNG/image URL set.
  bool get isPng => mode == VisemeMode.png;

  /// Create from a raw map of viseme key → SVG string.
  factory VisemeSet.fromMap(Map<String, String> svgMap) =>
      VisemeSet(svgMap, mode: VisemeMode.svg);

  /// Load from Flutter asset bundle.
  ///
  /// Expects a directory like `assets/heads/young_woman/` containing
  /// `sil.svg`, `PP.svg`, `FF.svg`, etc. (or .png equivalents).
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

    return VisemeSet(svgs, mode: VisemeMode.svg);
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
    return VisemeSet(svgs, mode: VisemeMode.svg);
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

    return VisemeSet(svgs, mode: VisemeMode.svg);
  }

  /// Create a PNG set from a CDN base URL.
  ///
  /// Doesn't download the images — just builds URL references that
  /// [Image.network] will fetch on demand.
  ///
  /// E.g., `fromCdnUrl('https://avatars.voxhelm.com/heads/friendly_robot')`
  static VisemeSet fromCdnUrl(String baseUrl, {String ext = 'png'}) {
    final base = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
    final urls = <String, String>{};
    for (final v in kAllVisemes) {
      urls[v] = '$base$v.$ext';
    }
    return VisemeSet(urls, mode: VisemeMode.png);
  }

  /// Load from a manifest URL, returning all available heads.
  ///
  /// The manifest is a JSON file at `{cdnBase}/manifest.json` with:
  /// ```json
  /// {"heads": [{"name": "friendly_robot", "ext": "png", ...}, ...]}
  /// ```
  static Future<Map<String, VisemeSet>> fromManifest(String cdnBase) async {
    final base = cdnBase.endsWith('/') ? cdnBase : '$cdnBase/';
    final response = await http.get(Uri.parse('${base}manifest.json'));
    if (response.statusCode != 200) {
      throw Exception('Failed to load manifest: ${response.statusCode}');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final heads = data['heads'] as List;
    final result = <String, VisemeSet>{};
    for (final h in heads) {
      final name = h['name'] as String;
      final ext = h['ext'] as String? ?? 'png';
      result[name] = VisemeSet.fromCdnUrl('$base$name', ext: ext);
    }
    return result;
  }
}
