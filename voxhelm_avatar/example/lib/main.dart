import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:voxhelm_avatar/voxhelm_avatar.dart';

void main() => runApp(const VoxhelmExampleApp());

/// Avatar metadata for the selection screen.
class AvatarInfo {
  final String id;
  final String label;
  final String assetPath;
  final AvatarStyle style;

  /// File extension for viseme frames.
  String get ext => style == AvatarStyle.photorealistic ? 'png' : 'svg';

  /// Eye positions for blink overlay (cartoon only, 512x512 SVG space).
  final Offset leftEyeCenter;
  final Offset rightEyeCenter;
  final double eyeRadiusX;
  final double eyeRadiusY;
  final Color eyelidColor;
  final Color eyelidStrokeColor;

  const AvatarInfo({
    required this.id,
    required this.label,
    required this.assetPath,
    required this.style,
    this.leftEyeCenter = const Offset(210, 240),
    this.rightEyeCenter = const Offset(302, 240),
    this.eyeRadiusX = 30,
    this.eyeRadiusY = 28,
    this.eyelidColor = const Color(0xFFF5C4A1),
    this.eyelidStrokeColor = const Color(0xFF3D2B1F),
  });
}

enum AvatarStyle { cartoon, photorealistic }

/// CDN base URL for avatar assets.
const _cdnBase = 'https://avatars.voxhelm.com/heads';

const _avatars = [
  AvatarInfo(id: 'young_woman', label: 'Young Woman', assetPath: '$_cdnBase/young_woman', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'young_man', label: 'Young Man', assetPath: '$_cdnBase/young_man', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'middle_woman', label: 'Middle Woman', assetPath: '$_cdnBase/middle_woman', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'middle_man', label: 'Middle Man', assetPath: '$_cdnBase/middle_man', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'older_woman', label: 'Older Woman', assetPath: '$_cdnBase/older_woman', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'older_man', label: 'Older Man', assetPath: '$_cdnBase/older_man', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'photo_man', label: 'Photo Man', assetPath: '$_cdnBase/photo_man', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'photo_woman', label: 'Photo Woman', assetPath: '$_cdnBase/photo_woman', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'chrome_bot', label: 'Chrome Bot', assetPath: '$_cdnBase/chrome_bot', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'bolt_bot', label: 'Bolt Bot', assetPath: '$_cdnBase/bolt_bot', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'mossling', label: 'Mossling', assetPath: '$_cdnBase/mossling', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'clayton', label: 'Clayton', assetPath: '$_cdnBase/clayton', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'nimbus', label: 'Nimbus', assetPath: '$_cdnBase/nimbus', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'clawford', label: 'Clawford', assetPath: '$_cdnBase/clawford', style: AvatarStyle.photorealistic),
  AvatarInfo(id: 'friendly_robot', label: 'Friendly Robot', assetPath: '$_cdnBase/friendly_robot', style: AvatarStyle.photorealistic),
];

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

class VoxhelmExampleApp extends StatelessWidget {
  const VoxhelmExampleApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Voxhelm Avatar',
        theme: ThemeData.dark(useMaterial3: true).copyWith(
          colorScheme: ColorScheme.dark(
            primary: const Color(0xFF4C9966),
            secondary: const Color(0xFF2A6644),
            surface: const Color(0xFF121212),
          ),
        ),
        home: const AvatarSelectionScreen(),
      );
}

// ---------------------------------------------------------------------------
// Avatar Selection Screen
// ---------------------------------------------------------------------------

class AvatarSelectionScreen extends StatelessWidget {
  const AvatarSelectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0D0D),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0D0D),
        title: const Text('Voxhelm Avatars'),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _SectionHeader(
            title: 'Avatars',
            subtitle: '${_avatars.length} presets — served from avatars.voxhelm.com',
          ),
          _AvatarGrid(avatars: _avatars),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  const _SectionHeader({required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12, top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Colors.white)),
          const SizedBox(height: 2),
          Text(subtitle,
              style: TextStyle(fontSize: 13, color: Colors.grey[500])),
        ],
      ),
    );
  }
}

class _AvatarGrid extends StatelessWidget {
  final List<AvatarInfo> avatars;
  const _AvatarGrid({required this.avatars});

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 0.85,
      ),
      itemCount: avatars.length,
      itemBuilder: (context, i) => _AvatarCard(info: avatars[i]),
    );
  }
}

class _AvatarCard extends StatefulWidget {
  final AvatarInfo info;
  const _AvatarCard({required this.info});

  @override
  State<_AvatarCard> createState() => _AvatarCardState();
}

class _AvatarCardState extends State<_AvatarCard> {
  // For cartoon: loaded SVG string. For photo: just a marker that loading is done.
  bool _loaded = false;
  String? _silSvg; // only used for cartoon

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) _loadThumbnail();
  }

  Future<void> _loadThumbnail() async {
    // All avatars now load from CDN — just mark as loaded immediately
    // and let Image.network handle the fetch.
    if (mounted) setState(() => _loaded = true);
  }

  @override
  Widget build(BuildContext context) {
    final isPhoto = widget.info.style == AvatarStyle.photorealistic;
    final badge = isPhoto ? 'PHOTO' : 'SVG';
    final badgeColor = isPhoto
        ? const Color(0xFF5B4FCF)
        : const Color(0xFF2A6644);

    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => AvatarPlayerScreen(info: widget.info),
        ),
      ),
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF1A1A1A),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFF2A2A2A)),
        ),
        child: Column(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius:
                    const BorderRadius.vertical(top: Radius.circular(16)),
                child: Image.network(
                            '${widget.info.assetPath}/sil.${widget.info.ext}',
                            fit: BoxFit.cover,
                            gaplessPlayback: true,
                            loadingBuilder: (context, child, progress) {
                              if (progress == null) return child;
                              return const Center(
                                child: CircularProgressIndicator(strokeWidth: 2));
                            },
                            errorBuilder: (_, __, ___) => const Center(
                              child: Icon(Icons.broken_image, color: Colors.grey)),
                          ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.info.label,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: badgeColor.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      badge,
                      style: TextStyle(
                        color: badgeColor,
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Avatar Player Screen
// ---------------------------------------------------------------------------

class AvatarPlayerScreen extends StatefulWidget {
  final AvatarInfo info;
  const AvatarPlayerScreen({super.key, required this.info});

  @override
  State<AvatarPlayerScreen> createState() => _AvatarPlayerScreenState();
}

class _AvatarPlayerScreenState extends State<AvatarPlayerScreen> {
  final _visemeCtrl = VisemeController();
  final _blinkCtrl = BlinkController();
  final _player = AudioPlayer();

  // For cartoon avatars — SVG-based rendering via VoxhelmAvatar widget.
  VisemeSet? _visemeSet;
  // For photorealistic avatars — PNG-based rendering.
  bool _photoLoaded = false;

  bool _playing = false;
  String _sentence = '';

  @override
  void initState() {
    super.initState();
    if (widget.info.style == AvatarStyle.cartoon) {
      _blinkCtrl.start();
    }

    _player.onPositionChanged.listen((pos) {
      _visemeCtrl.tick(pos.inMilliseconds / 1000.0);
    });
    _player.onPlayerComplete.listen((_) {
      setState(() => _playing = false);
      _visemeCtrl.reset();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_visemeSet == null && !_photoLoaded) _loadAssets();
  }

  Future<void> _loadAssets() async {
    if (widget.info.style == AvatarStyle.cartoon) {
      final set = await VisemeSet.fromAssetBundle(
        context,
        widget.info.assetPath,
      );
      setState(() => _visemeSet = set);
    } else {
      // Photo mode: build URL-based viseme set from CDN
      final set = VisemeSet.fromCdnUrl(widget.info.assetPath);
      // Precache images for smooth frame switching
      for (final url in set.assets.values) {
        try {
          await precacheImage(NetworkImage(url), context);
        } catch (_) {}
      }
      setState(() {
        _visemeSet = set;
        _photoLoaded = true;
      });
    }

    final raw = await DefaultAssetBundle.of(context)
        .loadString('assets/data/timeline.json');
    final json = jsonDecode(raw);
    final rawTimeline = json['timeline'] as List;
    final isLegacy = rawTimeline.isNotEmpty &&
        rawTimeline[0] is Map &&
        (rawTimeline[0] as Map).containsKey('start_ms');
    final timeline = isLegacy
        ? PhonemeTimeline.fromLegacy(rawTimeline.cast<Map<String, dynamic>>())
        : PhonemeTimeline.fromJson(rawTimeline);
    final sentence = json['sentence'] as String? ?? '';

    setState(() => _sentence = sentence);
    _visemeCtrl.setTimeline(timeline);
  }

  Future<void> _togglePlay() async {
    if (_playing) {
      await _player.pause();
      setState(() => _playing = false);
    } else {
      await _player.play(AssetSource('audio/audio.mp3'));
      setState(() => _playing = true);
    }
  }

  @override
  void dispose() {
    _visemeCtrl.dispose();
    _blinkCtrl.dispose();
    _player.dispose();
    super.dispose();
  }

  bool get _ready => _visemeSet != null;

  @override
  Widget build(BuildContext context) {
    final isCartoon = widget.info.style == AvatarStyle.cartoon;

    return Scaffold(
      backgroundColor: const Color(0xFF0D0D0D),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0D0D),
        title: Text(widget.info.label),
      ),
      body: !_ready
          ? const Center(child: CircularProgressIndicator())
          : Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (_sentence.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Text(
                      '\u201c$_sentence\u201d',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        fontStyle: FontStyle.italic,
                        color: Colors.grey[500],
                      ),
                    ),
                  ),
                const SizedBox(height: 24),
                Center(
                  child: _visemeSet != null
                      ? VoxhelmAvatar(
                          visemeSet: _visemeSet!,
                          controller: _visemeCtrl,
                          blinkController: isCartoon ? _blinkCtrl : null,
                          size: 280,
                          borderRadius: BorderRadius.circular(20),
                          leftEyeCenter: widget.info.leftEyeCenter,
                          rightEyeCenter: widget.info.rightEyeCenter,
                          eyeRadiusX: widget.info.eyeRadiusX,
                          eyeRadiusY: widget.info.eyeRadiusY,
                          eyelidColor: widget.info.eyelidColor,
                          eyelidStrokeColor: widget.info.eyelidStrokeColor,
                        )
                      : const SizedBox(width: 280, height: 280),
                ),
                const SizedBox(height: 12),
                // Style badge
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: isCartoon
                        ? const Color(0xFF1A3A2A)
                        : const Color(0xFF2A2545),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isCartoon
                          ? const Color(0xFF2A6644)
                          : const Color(0xFF5B4FCF),
                    ),
                  ),
                  child: Text(
                    isCartoon ? 'CARTOON SVG' : 'PHOTOREALISTIC',
                    style: TextStyle(
                      color: isCartoon
                          ? const Color(0xFF4C9966)
                          : const Color(0xFF8B7FE8),
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 2,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // Viseme badge
                ListenableBuilder(
                  listenable: _visemeCtrl,
                  builder: (context, _) => Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A3A2A),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: const Color(0xFF2A6644)),
                    ),
                    child: Text(
                      _visemeCtrl.currentViseme.toUpperCase(),
                      style: const TextStyle(
                        color: Color(0xFF4C9966),
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 2,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                FloatingActionButton.large(
                  onPressed: _togglePlay,
                  backgroundColor: const Color(0xFF2A6644),
                  child: Icon(
                    _playing ? Icons.pause : Icons.play_arrow,
                    size: 36,
                  ),
                ),
              ],
            ),
    );
  }
}

// ---------------------------------------------------------------------------
// Photorealistic PNG Avatar Widget
