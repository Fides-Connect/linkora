import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Aurora-style audio lens built for voice-first experiences.
/// Layers: breathing glow, orbital arcs, radial beams, particle sparks.
class AIBlobVisualizer extends StatefulWidget {
  final bool isListening;
  final bool isProcessing;
  final double size;
  final Color primaryColor;
  final Color secondaryColor;
  final Color accentColor;

  const AIBlobVisualizer({
    super.key,
    this.isListening = false,
    this.isProcessing = false,
    this.size = 200.0,
    this.primaryColor = const Color(0xFF00D4FF),
    this.secondaryColor = const Color(0xFF2563EB),
    this.accentColor = const Color(0xFF818CF8),
  });

  @override
  State<AIBlobVisualizer> createState() => _AIBlobVisualizerState();
}

class _AIBlobVisualizerState extends State<AIBlobVisualizer>
    with TickerProviderStateMixin {
  late AnimationController _coreController;
  late AnimationController _pulseController;
  late AnimationController _sparkController;

  @override
  void initState() {
    super.initState();

    _coreController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    )..repeat();

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat(reverse: true);

    _sparkController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3600),
    )..repeat();
  }

  @override
  void dispose() {
    _coreController.dispose();
    _pulseController.dispose();
    _sparkController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final combined = Listenable.merge([
      _coreController,
      _pulseController,
      _sparkController,
    ]);

    return AnimatedBuilder(
      animation: combined,
      builder: (context, _) {
        final breath = 1 + (_pulseController.value - 0.5) * 0.14;
        final listenBoost = widget.isListening ? 1.08 : 1.0;

        return Transform.scale(
          scale: breath * listenBoost,
          child: CustomPaint(
            size: Size.square(widget.size),
            painter: _AuroraPainter(
              t: _coreController.value,
              pulse: _pulseController.value,
              spark: _sparkController.value,
              isListening: widget.isListening,
              isProcessing: widget.isProcessing,
              primary: widget.primaryColor,
              secondary: widget.secondaryColor,
              accent: widget.accentColor,
            ),
          ),
        );
      },
    );
  }
}

class _AuroraPainter extends CustomPainter {
  final double t;
  final double pulse;
  final double spark;
  final bool isListening;
  final bool isProcessing;
  final Color primary;
  final Color secondary;
  final Color accent;

  _AuroraPainter({
    required this.t,
    required this.pulse,
    required this.spark,
    required this.isListening,
    required this.isProcessing,
    required this.primary,
    required this.secondary,
    required this.accent,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final baseR = size.width * 0.46;
    final glowR = baseR * (1.08 + (pulse - 0.5) * 0.08);

    _paintGlow(canvas, center, glowR);
    _paintArcs(canvas, center, baseR);
    _paintRays(canvas, center, baseR * 0.72);
    _paintOrbit(canvas, center, baseR * 0.62);
    _paintParticles(canvas, center, baseR * 0.78);
    _paintCore(canvas, center, baseR * 0.28);

    if (isProcessing) {
      _paintProcessingHalo(canvas, center, baseR * 0.88);
    }
  }

  void _paintGlow(Canvas canvas, Offset center, double radius) {
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [
          primary.withOpacity(0.08),
          secondary.withOpacity(0.05),
          Colors.transparent,
        ],
        stops: const [0.0, 0.6, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawCircle(center, radius, paint);
  }

  void _paintArcs(Canvas canvas, Offset center, double radius) {
    final arcPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = radius * 0.08
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [
          primary.withOpacity(0.9),
          secondary.withOpacity(0.4),
          accent.withOpacity(0.9),
        ],
      ).createShader(Rect.fromCircle(center: center, radius: radius));

    for (int i = 0; i < 3; i++) {
      final start = (t * 2 * math.pi * (1.2 + i * 0.1)) + i * 0.9;
      final sweep = math.pi * (0.7 + 0.3 * math.sin(pulse * 2 * math.pi + i));
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius * (0.92 - i * 0.12)),
        start,
        sweep,
        false,
        arcPaint..strokeWidth = radius * (0.08 - i * 0.012),
      );
    }
  }

  void _paintRays(Canvas canvas, Offset center, double radius) {
    final rays = 18;
    for (int i = 0; i < rays; i++) {
      final angle = (i / rays) * 2 * math.pi + t * 2 * math.pi * 0.6;
      final osc = 0.6 + 0.4 * math.sin(pulse * 2 * math.pi * 2 + i * 0.7);
      final inner = radius * 0.72;
      final outer = inner + radius * 0.12 * osc * (isListening ? 1.4 : 1.0);

      final p1 = center + Offset(math.cos(angle), math.sin(angle)) * inner;
      final p2 = center + Offset(math.cos(angle), math.sin(angle)) * outer;

      final paint = Paint()
        ..shader = LinearGradient(
          colors: [
            Colors.white.withOpacity(0.0),
            accent.withOpacity(0.35),
            primary.withOpacity(0.9),
          ],
        ).createShader(Rect.fromPoints(p1, p2))
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;

      canvas.drawLine(p1, p2, paint);
    }
  }

  void _paintOrbit(Canvas canvas, Offset center, double radius) {
    final orbitPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..color = Colors.white.withOpacity(isListening ? 0.4 : 0.22);

    canvas.drawCircle(center, radius, orbitPaint);

    // Moving dot along orbit
    final angle = (t * 2 * math.pi * 1.4) + spark * 2 * math.pi;
    final pos = center + Offset(math.cos(angle), math.sin(angle)) * radius;
    final dotPaint = Paint()
      ..color = primary.withOpacity(0.9)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
    canvas.drawCircle(pos, 4.5, dotPaint);
  }

  void _paintParticles(Canvas canvas, Offset center, double radius) {
    final count = 22;
    for (int i = 0; i < count; i++) {
      final angle = (i / count) * 2 * math.pi + spark * 2 * math.pi * 1.3;
      final depth = 0.08 * math.sin((spark * 2 * math.pi) + i * 0.9);
      final r = radius * (0.65 + depth);
      final pos = center + Offset(math.cos(angle), math.sin(angle)) * r;

      final size = 2.4 + 1.6 * (0.5 + 0.5 * math.sin(pulse * 2 * math.pi + i));
      final paint = Paint()
        ..color = i.isEven
            ? primary.withOpacity(0.65)
            : secondary.withOpacity(0.55)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
      canvas.drawCircle(pos, size, paint);
    }
  }

  void _paintCore(Canvas canvas, Offset center, double radius) {
    final innerPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.white.withOpacity(0.9),
          primary.withOpacity(0.9),
        ],
      ).createShader(Rect.fromCircle(center: center, radius: radius));

    canvas.drawCircle(center, radius, innerPaint);

    if (isListening) {
      final ringPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..shader = SweepGradient(
          colors: [
            primary.withOpacity(0.9),
            accent.withOpacity(0.4),
            secondary.withOpacity(0.9),
          ],
        ).createShader(Rect.fromCircle(center: center, radius: radius + 6));
      canvas.drawCircle(center, radius + 6, ringPaint);
    }
  }

  void _paintProcessingHalo(Canvas canvas, Offset center, double radius) {
    final segments = 5;
    final sweep = math.pi / 6;
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..color = accent.withOpacity(0.9);

    for (int i = 0; i < segments; i++) {
      final start = (spark * 2 * math.pi * 1.6) + i * (2 * math.pi / segments);
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        start,
        sweep,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _AuroraPainter oldDelegate) {
    return oldDelegate.t != t ||
        oldDelegate.pulse != pulse ||
        oldDelegate.spark != spark ||
        oldDelegate.isListening != isListening ||
        oldDelegate.isProcessing != isProcessing ||
        oldDelegate.primary != primary ||
        oldDelegate.secondary != secondary ||
        oldDelegate.accent != accent;
  }
}
