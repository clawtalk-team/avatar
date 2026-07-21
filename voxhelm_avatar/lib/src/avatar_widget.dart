import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import 'animation_frame_controller.dart';
import 'animation_mode_controller.dart';
import 'blink_controller.dart';
import 'viseme_controller.dart';
import 'models/viseme_set.dart';

/// A talking avatar widget that displays SVG faces synced to speech.
///
/// The widget switches between pre-generated SVG frames based on the current
/// viseme from [controller], and optionally overlays an eye-blink animation
/// driven by [blinkController].
///
/// When an [animationController] is provided, the widget applies per-group
/// SVG transforms (head tilt, eye movement, brow raises) for idle, listening,
/// and thinking animation modes.
///
/// ```dart
/// VoxhelmAvatar(
///   visemeSet: visemeSet,
///   controller: visemeController,
///   blinkController: blinkController,
///   animationController: animModeController,
///   size: 200,
/// )
/// ```
class VoxhelmAvatar extends StatefulWidget {
  /// The set of 15 SVG strings (one per viseme).
  final VisemeSet visemeSet;

  /// Controls which viseme frame is shown.
  final VisemeController controller;

  /// Optional controller for idle eye-blink animation.
  final BlinkController? blinkController;

  /// Optional controller for animation mode transforms (idle/listening/thinking).
  final AnimationModeController? animationController;

  /// Optional controller for pre-rendered animation frame cycling.
  ///
  /// When provided, non-speaking modes render the current animation frame
  /// from the CDN instead of applying SVG group transforms. Takes precedence
  /// over [animationController] for idle/listening/thinking states.
  final AnimationFrameController? animationFrameController;

  /// Widget size (width and height).
  final double size;

  /// Optional border radius.
  final BorderRadius? borderRadius;

  /// Background color behind the SVG.
  final Color backgroundColor;

  /// Left eye center in the 512x512 SVG coordinate space.
  final Offset leftEyeCenter;

  /// Right eye center in the 512x512 SVG coordinate space.
  final Offset rightEyeCenter;

  /// Eye horizontal radius in SVG space.
  final double eyeRadiusX;

  /// Eye vertical radius in SVG space (max value when fully closed).
  final double eyeRadiusY;

  /// Eyelid fill color. Should match the character's skin tone.
  final Color eyelidColor;

  /// Eyelid stroke color.
  final Color eyelidStrokeColor;

  const VoxhelmAvatar({
    super.key,
    required this.visemeSet,
    required this.controller,
    this.blinkController,
    this.animationController,
    this.animationFrameController,
    this.size = 200,
    this.borderRadius,
    this.backgroundColor = const Color(0xFF1A1A1A),
    this.leftEyeCenter = const Offset(210, 240),
    this.rightEyeCenter = const Offset(302, 240),
    this.eyeRadiusX = 30,
    this.eyeRadiusY = 28,
    this.eyelidColor = const Color(0xFFF5C4A1),
    this.eyelidStrokeColor = const Color(0xFF3D2B1F),
  });

  @override
  State<VoxhelmAvatar> createState() => _VoxhelmAvatarState();
}

class _VoxhelmAvatarState extends State<VoxhelmAvatar> {
  /// Pre-parsed SVG widgets keyed by viseme name (no animation transforms).
  final Map<String, Widget> _svgCache = {};

  /// Cache key for the last rendered animated SVG to avoid re-parsing.
  String? _lastAnimCacheKey;
  Widget? _lastAnimWidget;

  @override
  void initState() {
    super.initState();
    _buildSvgCache();
    widget.controller.addListener(_onUpdate);
    widget.blinkController?.addListener(_onUpdate);
    widget.animationController?.addListener(_onUpdate);
    widget.animationFrameController?.addListener(_onUpdate);
  }

  @override
  void didUpdateWidget(VoxhelmAvatar old) {
    super.didUpdateWidget(old);
    if (old.visemeSet != widget.visemeSet || old.size != widget.size) {
      _svgCache.clear();
      _buildSvgCache();
    }
    if (old.controller != widget.controller) {
      old.controller.removeListener(_onUpdate);
      widget.controller.addListener(_onUpdate);
    }
    if (old.blinkController != widget.blinkController) {
      old.blinkController?.removeListener(_onUpdate);
      widget.blinkController?.addListener(_onUpdate);
    }
    if (old.animationController != widget.animationController) {
      old.animationController?.removeListener(_onUpdate);
      widget.animationController?.addListener(_onUpdate);
    }
    if (old.animationFrameController != widget.animationFrameController) {
      old.animationFrameController?.removeListener(_onUpdate);
      widget.animationFrameController?.addListener(_onUpdate);
    }
  }

  void _buildSvgCache() {
    if (widget.visemeSet.isPng) {
      // PNG mode: build Image.network widgets
      for (final entry in widget.visemeSet.assets.entries) {
        _svgCache[entry.key] = Image.network(
          entry.value,
          width: widget.size,
          height: widget.size,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        );
      }
    } else {
      // SVG mode: parse SVG strings
      for (final entry in widget.visemeSet.svgs.entries) {
        _svgCache[entry.key] = SvgPicture.string(
          entry.value,
          width: widget.size,
          height: widget.size,
        );
      }
    }
  }

  void _onUpdate() => setState(() {});

  @override
  void dispose() {
    widget.controller.removeListener(_onUpdate);
    widget.blinkController?.removeListener(_onUpdate);
    widget.animationController?.removeListener(_onUpdate);
    widget.animationFrameController?.removeListener(_onUpdate);
    super.dispose();
  }

  /// Get the widget for the current viseme, with optional animation.
  Widget? _getVisemeWidget(String viseme) {
    final animCtrl = widget.animationController;
    final frameCtrl = widget.animationFrameController;

    // Check if we should show animation frames (non-speaking mode with frames available)
    if (frameCtrl != null && frameCtrl.isRunning) {
      final frameUrl = frameCtrl.currentFrameUrl;
      if (frameUrl != null) {
        // In non-speaking mode with animation frames, show the cycling frame
        return Image.network(
          frameUrl,
          width: widget.size,
          height: widget.size,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        );
      }
    }

    // Fast path: no SVG animation controller, speaking mode, or PNG mode
    if (animCtrl == null ||
        animCtrl.mode == AnimationMode.speaking ||
        !animCtrl.isRunning ||
        widget.visemeSet.isPng) {
      return _svgCache[viseme] ?? _svgCache['sil'];
    }

    // SVG animation: apply transforms by modifying the SVG string.
    // Quantize transform values to reduce re-parses (~10 updates/sec instead of 60).
    final transforms = animCtrl.transforms;
    final cacheKey = '$viseme|${transforms.entries.map((e) =>
        '${e.key}:${(e.value.tx * 2).round()},${(e.value.ty * 2).round()},'
        '${(e.value.r * 2).round()},${(e.value.sx * 100).round()},'
        '${(e.value.sy * 100).round()}').join('|')}';

    if (cacheKey == _lastAnimCacheKey && _lastAnimWidget != null) {
      return _lastAnimWidget;
    }

    final svgString = widget.visemeSet.svgs[viseme] ??
        widget.visemeSet.svgs['sil'];
    if (svgString == null) return null;

    final transformed = _injectTransforms(svgString, transforms);
    _lastAnimCacheKey = cacheKey;
    _lastAnimWidget = SvgPicture.string(
      transformed,
      width: widget.size,
      height: widget.size,
    );
    return _lastAnimWidget;
  }

  /// Inject transform attributes into SVG group tags.
  static String _injectTransforms(
    String svg,
    Map<String, GroupTransform> transforms,
  ) {
    var result = svg;
    for (final entry in transforms.entries) {
      final gid = entry.key;
      final t = entry.value;

      // Skip neutral transforms
      if (t == GroupTransform.neutral) continue;

      // Match <g id="head" ...> and inject/replace transform attribute
      final pattern = RegExp(
        r'''(<g\s+(?=[^>]*id\s*=\s*['"]''' +
            RegExp.escape(gid) +
            r'''['"])[^>]*?)(\s*/?>)''',
      );

      result = result.replaceFirstMapped(pattern, (match) {
        var tag = match.group(1)!;
        final close = match.group(2)!;

        // Remove existing transform attribute
        tag = tag.replaceAll(
          RegExp(r'''\s+transform\s*=\s*['"][^'"]*['"]'''),
          '',
        );

        // Build transform string
        // rotate around center of 512x512 viewBox
        final transform =
            'translate(${t.tx.toStringAsFixed(2)} ${t.ty.toStringAsFixed(2)}) '
            'rotate(${t.r.toStringAsFixed(2)} 256 256) '
            'scale(${t.sx.toStringAsFixed(4)} ${t.sy.toStringAsFixed(4)})';

        return '$tag transform="$transform"$close';
      });
    }
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final viseme = widget.controller.currentViseme;
    final visemeWidget = _getVisemeWidget(viseme);

    // SVG eyelid overlay only applies to SVG mode — PNG heads have their
    // own blink.png frame and Veo animation frames include natural blinks.
    final showBlinkOverlay = widget.blinkController != null &&
        widget.blinkController!.eyeClosedness > 0 &&
        widget.visemeSet.isSvg &&
        !(widget.animationFrameController?.currentFrameUrl != null);

    Widget child = Stack(
      children: [
        if (visemeWidget != null) visemeWidget,
        if (showBlinkOverlay)
          CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _BlinkPainter(
              closedness: widget.blinkController!.eyeClosedness,
              leftEye: widget.leftEyeCenter,
              rightEye: widget.rightEyeCenter,
              radiusX: widget.eyeRadiusX,
              radiusY: widget.eyeRadiusY,
              fillColor: widget.eyelidColor,
              strokeColor: widget.eyelidStrokeColor,
              canvasSize: 512, // SVG viewBox size
              widgetSize: widget.size,
            ),
          ),
      ],
    );

    if (widget.borderRadius != null) {
      child = ClipRRect(borderRadius: widget.borderRadius!, child: child);
    }

    return Container(
      width: widget.size,
      height: widget.size,
      color: widget.backgroundColor,
      child: child,
    );
  }
}

/// Paints eyelid ellipses over the eye positions to simulate blinking.
class _BlinkPainter extends CustomPainter {
  final double closedness;
  final Offset leftEye;
  final Offset rightEye;
  final double radiusX;
  final double radiusY;
  final Color fillColor;
  final Color strokeColor;
  final double canvasSize;
  final double widgetSize;

  _BlinkPainter({
    required this.closedness,
    required this.leftEye,
    required this.rightEye,
    required this.radiusX,
    required this.radiusY,
    required this.fillColor,
    required this.strokeColor,
    required this.canvasSize,
    required this.widgetSize,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final scale = widgetSize / canvasSize;
    final ry = radiusY * closedness;
    if (ry < 0.5) return;

    final fill = Paint()..color = fillColor;
    final stroke = Paint()
      ..color = strokeColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2 * scale;

    for (final eye in [leftEye, rightEye]) {
      final rect = Rect.fromCenter(
        center: Offset(eye.dx * scale, eye.dy * scale),
        width: radiusX * 2 * scale,
        height: ry * 2 * scale,
      );
      canvas.drawOval(rect, fill);
      canvas.drawOval(rect, stroke);
    }
  }

  @override
  bool shouldRepaint(_BlinkPainter old) => old.closedness != closedness;
}
