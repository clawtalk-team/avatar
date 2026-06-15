import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import 'blink_controller.dart';
import 'viseme_controller.dart';
import 'models/viseme_set.dart';

/// A talking avatar widget that displays SVG faces synced to speech.
///
/// The widget switches between pre-generated SVG frames based on the current
/// viseme from [controller], and optionally overlays an eye-blink animation
/// driven by [blinkController].
///
/// ```dart
/// VoxhelmAvatar(
///   visemeSet: visemeSet,
///   controller: visemeController,
///   blinkController: blinkController,
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
  /// Pre-parsed SVG widgets keyed by viseme name.
  final Map<String, Widget> _svgCache = {};

  @override
  void initState() {
    super.initState();
    _buildSvgCache();
    widget.controller.addListener(_onVisemeChange);
    widget.blinkController?.addListener(_onBlinkChange);
  }

  @override
  void didUpdateWidget(VoxhelmAvatar old) {
    super.didUpdateWidget(old);
    if (old.visemeSet != widget.visemeSet) {
      _svgCache.clear();
      _buildSvgCache();
    }
    if (old.controller != widget.controller) {
      old.controller.removeListener(_onVisemeChange);
      widget.controller.addListener(_onVisemeChange);
    }
    if (old.blinkController != widget.blinkController) {
      old.blinkController?.removeListener(_onBlinkChange);
      widget.blinkController?.addListener(_onBlinkChange);
    }
  }

  void _buildSvgCache() {
    for (final entry in widget.visemeSet.svgs.entries) {
      _svgCache[entry.key] = SvgPicture.string(
        entry.value,
        width: widget.size,
        height: widget.size,
      );
    }
  }

  void _onVisemeChange() => setState(() {});
  void _onBlinkChange() => setState(() {});

  @override
  void dispose() {
    widget.controller.removeListener(_onVisemeChange);
    widget.blinkController?.removeListener(_onBlinkChange);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final viseme = widget.controller.currentViseme;
    final svgWidget = _svgCache[viseme] ?? _svgCache['sil'];

    Widget child = Stack(
      children: [
        if (svgWidget != null) svgWidget,
        if (widget.blinkController != null &&
            widget.blinkController!.eyeClosedness > 0)
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
