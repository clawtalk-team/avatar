import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:audioplayers/audioplayers.dart';

void main() => runApp(const AvatarDemoApp());

class AvatarDemoApp extends StatelessWidget {
  const AvatarDemoApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Avatar Demo',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF5C3A1E)),
        ),
        home: const AvatarScreen(),
      );
}

// ── Viseme shapes: [jaw_open, lip_spread, lip_part] ──────────────────────────
const Map<String, List<double>> kVisemeShapes = {
  'sil': [0.00,  0.00,  0.00],
  'PP':  [0.00,  0.00, -0.20],
  'FF':  [0.05,  0.15,  0.20],
  'TH':  [0.10,  0.00,  0.30],
  'DD':  [0.15,  0.10,  0.30],
  'kk':  [0.20,  0.00,  0.25],
  'CH':  [0.12, -0.35,  0.28],
  'SS':  [0.05,  0.50,  0.12],
  'nn':  [0.10,  0.05,  0.20],
  'RR':  [0.15, -0.28,  0.25],
  'aa':  [0.85,  0.15,  0.80],
  'E':   [0.40,  0.30,  0.50],
  'I':   [0.05,  0.55,  0.10],
  'O':   [0.45, -0.40,  0.52],
  'U':   [0.18, -0.65,  0.28],
};

// ── Timeline frame ────────────────────────────────────────────────────────────
class VisemeFrame {
  final String viseme;
  final int startMs;
  final int endMs;
  const VisemeFrame(this.viseme, this.startMs, this.endMs);
}

List<VisemeFrame> framesFromJson(List<dynamic> raw) => raw
    .map((e) => VisemeFrame(
          e['viseme'] as String,
          e['start_ms'] as int,
          e['end_ms'] as int,
        ))
    .toList();

String visemeAtMs(List<VisemeFrame> frames, int ms) {
  for (final f in frames) {
    if (ms >= f.startMs && ms < f.endMs) return f.viseme;
  }
  return 'sil';
}

// ── Lerp / smoothstep ─────────────────────────────────────────────────────────
double lerp(double a, double b, double t) => a + (b - a) * t;
double smoothstep(double t) {
  t = t.clamp(0.0, 1.0);
  return t * t * (3 - 2 * t);
}

// ── Avatar screen ─────────────────────────────────────────────────────────────
class AvatarScreen extends StatefulWidget {
  const AvatarScreen({super.key});
  @override
  State<AvatarScreen> createState() => _AvatarScreenState();
}

class _AvatarScreenState extends State<AvatarScreen>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  late final AudioPlayer _player;

  List<VisemeFrame> _timeline = [];
  String _sentence = '';

  // Interpolation state — mirrors JS demo
  List<double> _prevShape = [0, 0, 0];
  List<double> _targShape = [0, 0, 0];
  List<double> _interp    = [0, 0, 0];
  int _transStartMs       = -999999;
  String _targetViseme    = 'sil';
  static const int _transitionMs = 55;

  bool _playing    = false;
  double _progress = 0.0;
  Duration _audioPos = Duration.zero;
  Duration _audioDur = Duration.zero;

  @override
  void initState() {
    super.initState();
    _player = AudioPlayer();
    _player.onPositionChanged.listen((pos) {
      if (mounted) _audioPos = pos;
    });
    _player.onDurationChanged.listen((dur) {
      if (mounted) _audioDur = dur;
    });
    _player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playing = false);
    });

    _ticker = createTicker(_onTick)..start();
    _loadData();
  }

  Future<void> _loadData() async {
    final raw = await DefaultAssetBundle.of(context)
        .loadString('assets/data/timeline.json');
    final json = jsonDecode(raw) as Map<String, dynamic>;
    if (!mounted) return;
    setState(() {
      _timeline = framesFromJson(json['timeline'] as List);
      _sentence = json['sentence'] as String;
    });
  }

  void _onTick(Duration _) {
    if (!mounted) return;
    final ms = _audioPos.inMilliseconds;
    final v  = visemeAtMs(_timeline, ms);

    if (v != _targetViseme) {
      _prevShape    = List.of(_interp);
      _targShape    = kVisemeShapes[v] ?? kVisemeShapes['sil']!;
      _transStartMs = ms;
      _targetViseme = v;
    }

    final t = smoothstep((ms - _transStartMs) / _transitionMs);
    _interp = [
      lerp(_prevShape[0], _targShape[0], t),
      lerp(_prevShape[1], _targShape[1], t),
      lerp(_prevShape[2], _targShape[2], t),
    ];

    final durMs = _audioDur.inMilliseconds;
    _progress = durMs > 0 ? (ms / durMs).clamp(0.0, 1.0) : 0.0;

    setState(() {});
  }

  Future<void> _togglePlay() async {
    if (_playing) {
      await _player.pause();
      setState(() => _playing = false);
    } else {
      if (_audioDur > Duration.zero && _audioPos >= _audioDur) {
        await _player.seek(Duration.zero);
      }
      await _player.play(AssetSource('audio/audio.mp3'));
      setState(() => _playing = true);
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0EDE8),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF0EDE8),
        elevation: 0,
        title: const Text(
          'Avatar Demo',
          style: TextStyle(color: Color(0xFF2A1A0A), fontWeight: FontWeight.w600),
        ),
      ),
      body: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (_sentence.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
              child: Text(
                '\u201c$_sentence\u201d',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 15,
                  fontStyle: FontStyle.italic,
                  color: Color(0xFF5C3A1E),
                ),
              ),
            ),
          const SizedBox(height: 16),
          Center(
            child: SizedBox(
              width: 300,
              height: 300,
              child: CustomPaint(
                painter: AvatarPainter(
                  jaw:    _interp[0],
                  spread: _interp[1],
                  part:   _interp[2],
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          // Viseme badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFF5C3A1E),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              _targetViseme.toUpperCase(),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 20),
          // Progress bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 48),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _progress,
                minHeight: 8,
                backgroundColor: const Color(0xFFD9D0C8),
                valueColor: const AlwaysStoppedAnimation(Color(0xFF5C3A1E)),
              ),
            ),
          ),
          const SizedBox(height: 20),
          // Play / pause
          FloatingActionButton(
            onPressed: _togglePlay,
            backgroundColor: const Color(0xFF5C3A1E),
            foregroundColor: Colors.white,
            child: Icon(_playing ? Icons.pause : Icons.play_arrow, size: 32),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

// ── Avatar painter ────────────────────────────────────────────────────────────
//
// All coordinates are in a 512×512 logical space (matching svg_generator.py).
// The canvas is scaled to fit the widget's actual size.
//
class AvatarPainter extends CustomPainter {
  final double jaw;
  final double spread;
  final double part;
  const AvatarPainter({required this.jaw, required this.spread, required this.part});

  // ── Constants from svg_generator.py ─────────────────────────────────────────
  static const double W = 512, H = 512;
  static const double CX = 256, CY = 256;
  static const double headRX = 148, headRY = 192, headCY = CY + 6;
  static const double hairlineY = headCY - 108;
  static const double hairRX = headRX + 16, hairRY = headRY + 22, hairECY = headCY - 48;
  static const double eyeY = headCY - 50, eyeOffset = 60;
  static const double eyeRX = 28, eyeRY = 24, irisR = 14, pupilR = 7;
  static const double noseCX = CX, noseCY = headCY + 22;
  static const double mouthCX = CX, mouthCY = headCY + 78;
  static const double mwHalf = 54, mhHalf = 10;

  // ── Colours ──────────────────────────────────────────────────────────────────
  static const _skinLight = Color(0xFFFDD8BC);
  static const _skin      = Color(0xFFF5C5A3);
  static const _skinDark  = Color(0xFFE8A87C);
  static const _hairDark  = Color(0xFF3A2010);
  static const _hairLight = Color(0xFF7A5030);
  static const _hairMid   = Color(0xFF5C3A1E);
  static const _outline   = Color(0xFF2A1A0A);
  static const _lipUpper  = Color(0xFFD4806A);
  static const _lipLower  = Color(0xFFC06050);
  static const _mouthDark = Color(0xFF1A0A08);
  static const _teeth     = Color(0xFFF5F0E8);
  static const _tongue    = Color(0xFFC85050);
  static const _cheek     = Color(0xFFF0A898);
  static const _bg        = Color(0xFFF0EDE8);

  @override
  void paint(Canvas canvas, Size size) {
    final scale = math.min(size.width / W, size.height / H);
    canvas.translate(
      (size.width  - W * scale) / 2,
      (size.height - H * scale) / 2,
    );
    canvas.scale(scale);

    _drawBg(canvas);
    _drawNeck(canvas);
    _drawEars(canvas);
    _drawHair(canvas);
    _drawHead(canvas);
    _drawEyebrows(canvas);
    _drawEyes(canvas);
    _drawNose(canvas);
    _drawCheeks(canvas);
    _drawMouth(canvas);
  }

  void _drawBg(Canvas canvas) =>
      canvas.drawRect(const Rect.fromLTWH(0, 0, W, H), Paint()..color = _bg);

  void _drawNeck(Canvas canvas) {
    final rr = RRect.fromRectAndRadius(
      const Rect.fromLTWH(218, 432, 76, 85),
      const Radius.circular(20),
    );
    canvas.drawRRect(rr, Paint()..color = _skin);
    canvas.drawRRect(rr, _stroke(_outline, 2.5));
  }

  void _drawEars(Canvas canvas) {
    for (final cx in [CX - eyeOffset - 40.0, CX + eyeOffset + 40.0]) {
      final r = Rect.fromCenter(center: Offset(cx, 250), width: 30, height: 48);
      canvas.drawOval(r, Paint()..color = _skin);
      canvas.drawOval(r, _stroke(_outline, 2.5));
    }
  }

  void _drawHair(Canvas canvas) {
    final hairRect = Rect.fromCenter(
      center: const Offset(CX, hairECY),
      width:  hairRX * 2,
      height: hairRY * 2,
    );
    final hairPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.2, -0.4),
        radius: 0.6,
        colors: [_hairLight, _hairDark],
      ).createShader(hairRect);

    // Top / bulk — clip above hairline
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, W, hairlineY));
    canvas.drawOval(hairRect, hairPaint);
    canvas.restore();

    // Sideburns — clip below hairline
    final sideRect = Rect.fromLTWH(0, hairlineY, W, H - hairlineY);
    for (final cx in [CX - headRX + 4.0, CX + headRX - 4.0]) {
      canvas.save();
      canvas.clipRect(sideRect);
      canvas.drawOval(
        Rect.fromCenter(center: Offset(cx, hairlineY + 28), width: 36, height: 56),
        Paint()..color = _hairMid,
      );
      canvas.restore();
    }
  }

  void _drawHead(Canvas canvas) {
    final r = Rect.fromCenter(
      center: const Offset(CX, headCY),
      width:  headRX * 2,
      height: headRY * 2,
    );
    canvas.drawOval(
      r,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.15, -0.25),
          radius: 0.6,
          colors: [_skinLight, _skin, _skinDark],
          stops: const [0.0, 0.65, 1.0],
        ).createShader(r),
    );
    canvas.drawOval(r, _stroke(_outline, 3.0));
  }

  void _drawEyebrows(Canvas canvas) {
    final p = _stroke(_hairMid, 5)
      ..strokeCap = StrokeCap.round;
    for (final sign in [-1.0, 1.0]) {
      final cx = CX + sign * eyeOffset;
      canvas.drawPath(
        Path()
          ..moveTo(cx - 20, eyeY - 36)
          ..quadraticBezierTo(cx, eyeY - 44, cx + 20, eyeY - 34),
        p,
      );
    }
  }

  void _drawEyes(Canvas canvas) {
    for (final sign in [-1.0, 1.0]) {
      final cx = CX + sign * eyeOffset;
      final r = Rect.fromCenter(
        center: Offset(cx, eyeY),
        width:  eyeRX * 2,
        height: eyeRY * 2,
      );
      canvas.drawOval(r, Paint()..color = Colors.white);
      canvas.drawOval(r, _stroke(_outline, 2.5));
      canvas.drawCircle(Offset(cx, eyeY), irisR, Paint()..color = _hairMid);
      canvas.drawCircle(Offset(cx, eyeY), irisR, _stroke(_outline, 1.5));
      canvas.drawCircle(Offset(cx, eyeY), pupilR, Paint()..color = _outline);
      canvas.drawCircle(Offset(cx + 6, eyeY - 6), 4,
          Paint()..color = Colors.white.withOpacity(0.85));
    }
  }

  void _drawNose(Canvas canvas) {
    final r = Rect.fromCenter(
      center: const Offset(noseCX, noseCY),
      width: 20, height: 14,
    );
    canvas.drawOval(r, Paint()..color = _skinDark.withOpacity(0.6));
    canvas.drawOval(r, _stroke(_outline, 1.5));
    for (final dx in [-7.0, 7.0]) {
      canvas.drawOval(
        Rect.fromCenter(center: Offset(noseCX + dx, noseCY + 3), width: 10, height: 7),
        Paint()..color = _outline.withOpacity(0.35),
      );
    }
  }

  void _drawCheeks(Canvas canvas) {
    for (final sign in [-1.0, 1.0]) {
      final cx = CX + sign * 68;
      final r  = Rect.fromCenter(center: Offset(cx, headCY - 6), width: 60, height: 34);
      canvas.drawOval(r, Paint()
        ..shader = RadialGradient(
          colors: [_cheek.withOpacity(0.5), _cheek.withOpacity(0)],
        ).createShader(r));
    }
  }

  // ── Mouth geometry — port of svg_generator.compute_mouth() ──────────────────
  Map<String, double> _computeMouth() {
    final spreadDx = spread * mwHalf * 0.38;
    final lx = mouthCX - mwHalf + spreadDx;
    final rx = mouthCX + mwHalf - spreadDx;
    final jawDy = jaw * 52;
    final cornerY = mouthCY + (-spread * 6);
    final upperOpen = part >= 0 ? part * mhHalf * 0.9  : part * mhHalf * 0.4;
    final lowerOpen = part >= 0 ? part * mhHalf * 1.4  : part * mhHalf * 0.6;
    final puckerDy  = math.max(0.0, -spread) * 5;
    return {
      'lx':        lx,
      'rx':        rx,
      'utop':      cornerY - mhHalf * 1.2 - upperOpen - puckerDy,
      'ubot':      cornerY - upperOpen,
      'ltop':      cornerY + jawDy + lowerOpen,
      'lbot':      cornerY + jawDy + mhHalf * 1.2 + lowerOpen,
      'cy':        cornerY,
      'cs':        (rx - lx) * 0.28,
    };
  }

  void _drawMouth(Canvas canvas) {
    final m  = _computeMouth();
    final lx = m['lx']!, rx = m['rx']!;
    final utop = m['utop']!, ubot = m['ubot']!;
    final ltop = m['ltop']!, lbot = m['lbot']!;
    final cy = m['cy']!, cs = m['cs']!;
    final cx = (lx + rx) / 2;
    final w  = rx - lx;
    final gap = ltop - ubot;

    // Cavity
    if (gap >= 4) {
      final my = (ubot + ltop) / 2;
      canvas.drawPath(
        Path()
          ..moveTo(lx, my)
          ..cubicTo(cx - cs, ubot,  cx + cs, ubot,  rx, my)
          ..cubicTo(cx + cs, ltop,  cx - cs, ltop,  lx, my)
          ..close(),
        Paint()..color = _mouthDark.withOpacity(0.88),
      );
    }

    // Teeth
    if (gap >= 6) {
      final tlx = lx + 6, trx = rx - 6;
      final tt  = ubot + 1;
      final tb  = math.min(ltop - 1, tt + gap * 0.45);
      if (tb > tt) {
        final tcx = (tlx + trx) / 2, tcs = (trx - tlx) * 0.15;
        canvas.drawPath(
          Path()
            ..moveTo(tlx, tt)
            ..cubicTo(tcx - tcs, tt - 2,  tcx + tcs, tt - 2,  trx, tt)
            ..lineTo(trx, tb)
            ..cubicTo(tcx + tcs, tb + 2,  tcx - tcs, tb + 2,  tlx, tb)
            ..close(),
          Paint()..color = _teeth,
        );
      }
    }

    // Tongue
    if (gap >= 20 && jaw >= 0.35) {
      final tt = ubot + gap * 0.55, tb = ltop - 2;
      if (tb > tt) {
        final hw = w * 0.30;
        canvas.drawPath(
          Path()
            ..moveTo(mouthCX - hw, tb)
            ..cubicTo(mouthCX - hw * 1.1, tt,  mouthCX + hw * 1.1, tt,  mouthCX + hw, tb)
            ..cubicTo(mouthCX + hw * 0.5, tb + 8,  mouthCX - hw * 0.5, tb + 8,  mouthCX - hw, tb)
            ..close(),
          Paint()..color = _tongue.withOpacity(0.90),
        );
      }
    }

    // Upper lip
    final ul = Path()
      ..moveTo(lx, cy)
      ..cubicTo(lx + cs, utop + 4,  cx - w * 0.22 - 8, utop - 2,  cx, utop + 5)
      ..cubicTo(cx + w * 0.22 + 8, utop - 2,  rx - cs, utop + 4,  rx, cy)
      ..cubicTo(rx - cs * 0.6, ubot,  lx + cs * 0.6, ubot,  lx, cy)
      ..close();
    canvas.drawPath(ul, Paint()..color = _lipUpper);
    canvas.drawPath(ul, _stroke(_outline, 2)..strokeJoin = StrokeJoin.round);

    // Lower lip
    final ll = Path()
      ..moveTo(lx, cy)
      ..cubicTo(lx + cs * 0.6, ltop,  rx - cs * 0.6, ltop,  rx, cy)
      ..cubicTo(rx - cs, lbot,  lx + cs, lbot,  lx, cy)
      ..close();
    canvas.drawPath(ll, Paint()..color = _lipLower);
    canvas.drawPath(ll, _stroke(_outline, 2)..strokeJoin = StrokeJoin.round);

    // Highlight
    final hilRX = w * 0.5 * 0.4;
    canvas.drawOval(
      Rect.fromCenter(center: Offset(cx, utop), width: hilRX * 2, height: 6),
      Paint()..color = Colors.white.withOpacity(0.30),
    );
  }

  static Paint _stroke(Color c, double w) => Paint()
    ..color = c
    ..style = PaintingStyle.stroke
    ..strokeWidth = w;

  @override
  bool shouldRepaint(AvatarPainter old) =>
      old.jaw != jaw || old.spread != spread || old.part != part;
}
