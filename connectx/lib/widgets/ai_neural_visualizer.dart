import 'dart:math' as math;
import 'package:flutter/material.dart';

class AINeuralVisualizer extends StatefulWidget {
  final bool isListening;
  final bool isProcessing;
  final double size;
  final Color primaryColor;
  final Color secondaryColor;
  final Color accentColor;

  const AINeuralVisualizer({
    super.key,
    required this.isListening,
    required this.isProcessing,
    this.size = 300,
    this.primaryColor = const Color(0xFF00D4FF),
    this.secondaryColor = const Color(0xFF6C63FF),
    this.accentColor = const Color(0xFF818CF8),
  });

  @override
  State<AINeuralVisualizer> createState() => _AINeuralVisualizerState();
}

class _AINeuralVisualizerState extends State<AINeuralVisualizer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  final List<_Particle> _particles = [];
  final int _particleCount = 60;
  final math.Random _random = math.Random();

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();

    _initializeParticles();
  }

  void _initializeParticles() {
    for (int i = 0; i < _particleCount; i++) {
      _particles.add(_createParticle());
    }
  }

  _Particle _createParticle() {
    final angle = _random.nextDouble() * 2 * math.pi;
    final radius = _random.nextDouble() * 0.5; // Normalized radius 0.0 to 0.5
    return _Particle(
      angle: angle,
      radius: radius,
      speed: 0.2 + _random.nextDouble() * 0.5,
      size: 2.0 + _random.nextDouble() * 3.0,
      color: _random.nextBool() ? widget.primaryColor : widget.secondaryColor,
      opacity: 0.3 + _random.nextDouble() * 0.7,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return CustomPaint(
          size: Size(widget.size, widget.size),
          painter: _NeuralPainter(
            particles: _particles,
            animationValue: _controller.value,
            isListening: widget.isListening,
            isProcessing: widget.isProcessing,
            primaryColor: widget.primaryColor,
            accentColor: widget.accentColor,
          ),
        );
      },
    );
  }
}

class _Particle {
  double angle;
  double radius;
  double speed;
  double size;
  Color color;
  double opacity;

  _Particle({
    required this.angle,
    required this.radius,
    required this.speed,
    required this.size,
    required this.color,
    required this.opacity,
  });
}

class _NeuralPainter extends CustomPainter {
  final List<_Particle> particles;
  final double animationValue;
  final bool isListening;
  final bool isProcessing;
  final Color primaryColor;
  final Color accentColor;

  _NeuralPainter({
    required this.particles,
    required this.animationValue,
    required this.isListening,
    required this.isProcessing,
    required this.primaryColor,
    required this.accentColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final maxRadius = size.width / 2;

    // Draw connecting lines
    final linePaint = Paint()
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    // Update and draw particles
    for (var i = 0; i < particles.length; i++) {
      var particle = particles[i];

      // Update logic based on state
      if (isProcessing) {
        // Swirl rapidly towards center
        particle.angle += 0.0005 * particle.speed;
        particle.radius = (particle.radius - 0.005);
        if (particle.radius < 0.1) particle.radius = 0.5;
      } else if (isListening) {
        // Expand and rotate faster
        particle.angle += 0.02 * particle.speed;
        particle.radius = 0.3 + 0.2 * math.sin(animationValue * 2 * math.pi + i);
      } else {
        // Idle float
        particle.angle += 0.005 * particle.speed;
        // Gentle breathing
        particle.radius = particle.radius; 
      }

      // Calculate position
      final r = particle.radius * maxRadius;
      final x = center.dx + r * math.cos(particle.angle);
      final y = center.dy + r * math.sin(particle.angle);
      final position = Offset(x, y);

      // Draw connections to nearby particles
      if (!isProcessing) { // Don't draw lines when swirling fast
        for (var j = i + 1; j < particles.length; j++) {
          final other = particles[j];
          final otherR = other.radius * maxRadius;
          final otherX = center.dx + otherR * math.cos(other.angle);
          final otherY = center.dy + otherR * math.sin(other.angle);
          final otherPos = Offset(otherX, otherY);

          final dist = (position - otherPos).distance;
          if (dist < 40) {
            linePaint.color = particle.color.withValues(alpha: (1 - dist / 40) * 0.3);
            canvas.drawLine(position, otherPos, linePaint);
          }
        }
      }

      // Draw particle
      final paint = Paint()
        ..color = (isProcessing ? accentColor : particle.color).withValues(alpha: particle.opacity)
        ..style = PaintingStyle.fill;
      
      // Glow effect
      if (isListening) {
        canvas.drawCircle(
          position, 
          particle.size * 1.5, 
          Paint()..color = particle.color.withValues(alpha: 0.2)
        );
      }

      canvas.drawCircle(position, particle.size, paint);
    }
    
    // Draw central core if processing
    if (isProcessing) {
       canvas.drawCircle(
         center, 
         20, 
         Paint()
           ..color = accentColor.withValues(alpha: 0.5)
           ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10)
       );
       canvas.drawCircle(center, 10, Paint()..color = Colors.white);
    }
  }

  @override
  bool shouldRepaint(covariant _NeuralPainter oldDelegate) => true;
}
