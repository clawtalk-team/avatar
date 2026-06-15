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

const _avatars = [
  AvatarInfo(
    id: 'young_woman',
    label: 'Young Woman',
    assetPath: 'assets/heads/young_woman',
    style: AvatarStyle.cartoon,
  ),
  AvatarInfo(
    id: 'young_man',
    label: 'Young Man',
    assetPath: 'assets/heads/young_man',
    style: AvatarStyle.cartoon,
    eyelidColor: Color(0xFFD4A574),
    eyelidStrokeColor: Color(0xFF2D1F14),
  ),
  AvatarInfo(
    id: 'middle_woman',
    label: 'Middle Woman',
    assetPath: 'assets/heads/middle_woman',
    style: AvatarStyle.cartoon,
  ),
  AvatarInfo(
    id: 'middle_man',
    label: 'Middle Man',
    assetPath: 'assets/heads/middle_man',
    style: AvatarStyle.cartoon,
    eyelidColor: Color(0xFF8B6B4E),
    eyelidStrokeColor: Color(0xFF3D2B1F),
  ),
  AvatarInfo(
    id: 'older_woman',
    label: 'Older Woman',
    assetPath: 'assets/heads/older_woman',
    style: AvatarStyle.cartoon,
  ),
  AvatarInfo(
    id: 'older_man',
    label: 'Older Man',
    assetPath: 'assets/heads/older_man',
    style: AvatarStyle.cartoon,
    eyelidColor: Color(0xFFD4A574),
    eyelidStrokeColor: Color(0xFF2D1F14),
  ),
  AvatarInfo(
    id: 'flash_woman',
    label: 'Flash Woman',
    assetPath: 'assets/heads/flash_woman',
    style: AvatarStyle.photorealistic,
  ),
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
    final cartoon =
        _avatars.where((a) => a.style == AvatarStyle.cartoon).toList();
    final photo =
        _avatars.where((a) => a.style == AvatarStyle.photorealistic).toList();

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
            title: 'Cartoon',
            subtitle: '${cartoon.length} avatars — vector SVG',
          ),
          _AvatarGrid(avatars: cartoon),
          const SizedBox(height: 24),
          _SectionHeader(
            title: 'Photorealistic',
            subtitle: '${photo.length} avatars — Gemini Flash Image',
          ),
          _AvatarGrid(avatars: photo),
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
    if (widget.info.style == AvatarStyle.photorealistic) {
      // PNG — just mark as loaded, Image.asset handles rendering.
      if (mounted) setState(() => _loaded = true);
      return;
    }
    try {
      final svg = await DefaultAssetBundle.of(context)
          .loadString('${widget.info.assetPath}/sil.svg');
      if (mounted) setState(() { _silSvg = svg; _loaded = true; });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
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
                child: !_loaded
                    ? const Center(
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : isPhoto
                        ? Image.asset(
                            '${widget.info.assetPath}/sil.png',
                            fit: BoxFit.cover,
                          )
                        : _silSvg != null
                            ? SvgPicture.string(_silSvg!, fit: BoxFit.cover)
                            : const Center(
                                child: Icon(Icons.broken_image,
                                    color: Colors.grey)),
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
      // Precache all viseme PNGs.
      for (final v in kAllVisemes) {
        // ignore errors for missing visemes
        try {
          await precacheImage(
            AssetImage('${widget.info.assetPath}/$v.png'),
            context,
          );
        } catch (_) {}
      }
      setState(() => _photoLoaded = true);
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

  bool get _ready =>
      widget.info.style == AvatarStyle.cartoon
          ? _visemeSet != null
          : _photoLoaded;

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
                  child: isCartoon
                      ? VoxhelmAvatar(
                          visemeSet: _visemeSet!,
                          controller: _visemeCtrl,
                          blinkController: _blinkCtrl,
                          size: 280,
                          borderRadius: BorderRadius.circular(20),
                          leftEyeCenter: widget.info.leftEyeCenter,
                          rightEyeCenter: widget.info.rightEyeCenter,
                          eyeRadiusX: widget.info.eyeRadiusX,
                          eyeRadiusY: widget.info.eyeRadiusY,
                          eyelidColor: widget.info.eyelidColor,
                          eyelidStrokeColor: widget.info.eyelidStrokeColor,
                        )
                      : _PhotoAvatar(
                          assetPath: widget.info.assetPath,
                          controller: _visemeCtrl,
                          size: 280,
                        ),
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
// ---------------------------------------------------------------------------

/// Displays a photorealistic avatar by swapping between pre-rendered PNG
/// images (one per viseme) driven by a [VisemeController].
class _PhotoAvatar extends StatelessWidget {
  final String assetPath;
  final VisemeController controller;
  final double size;

  const _PhotoAvatar({
    required this.assetPath,
    required this.controller,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final viseme = controller.currentViseme;
        return ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: SizedBox(
            width: size,
            height: size,
            child: Image.asset(
              '$assetPath/$viseme.png',
              width: size,
              height: size,
              fit: BoxFit.cover,
              // Fall back to sil if the viseme image doesn't exist.
              errorBuilder: (_, __, ___) => Image.asset(
                '$assetPath/sil.png',
                width: size,
                height: size,
                fit: BoxFit.cover,
              ),
            ),
          ),
        );
      },
    );
  }
}
