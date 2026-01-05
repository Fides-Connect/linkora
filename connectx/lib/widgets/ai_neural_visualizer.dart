import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../utils/constants.dart';

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
    this.size = AppConstants.neuralVisualizerSize,
    this.primaryColor = AppConstants.primaryCyan,
    this.secondaryColor = AppConstants.primaryPurple,
    this.accentColor = AppConstants.accentPurple,
  });

  @override
  State<AINeuralVisualizer> createState() => _AINeuralVisualizerState();
}

class _AINeuralVisualizerState extends State<AINeuralVisualizer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  final List<_Particle> _particles = [];
  final int _particleCount = AppConstants.particleCount;
  final math.Random _random = math.Random();

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: AppConstants.neuralAnimationDuration,
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
    final radius = _random.nextDouble() * 0.4; // Smaller spread
    final baseSpeed = 0.1 + _random.nextDouble() * 0.2;
    
    return _Particle(
      angle: angle,
      radius: radius,
      speed: baseSpeed,
      currentSpeed: baseSpeed * 0.002, // Start at idle speed
      size: 2.0 + _random.nextDouble() * 2.0, // Smaller particles
      color: Colors.white,
      opacity: 0.3 + _random.nextDouble() * 0.4, // Varying transparency
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
  double currentSpeed; // Current rotation speed for smooth transitions
  double size;
  Color color;
  double opacity;

  _Particle({
    required this.angle,
    required this.radius,
    required this.speed,
    required this.currentSpeed,
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

    // Draw soft central glow
    final glowPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.08)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 30);
    canvas.drawCircle(center, 60, glowPaint);

    // Update and draw particles
    for (var i = 0; i < particles.length; i++) {
      var particle = particles[i];

      // Gentle breathing animation
      final breathe = math.sin(animationValue * 2 * math.pi) * 0.05;
      
      // Define target speeds for each state
      double targetSpeed;
      double targetRadius;
      
      if (isProcessing) {
        // Processing: moderate speed, compact
        targetSpeed = particle.speed * 0.005;
        targetRadius = 0.25 + breathe + 0.1 * math.sin(animationValue * 2 * math.pi + i);
      } else if (isListening) {
        // Listening: fast, energetic motion
        targetSpeed = particle.speed * 0.025; // 12.5x faster than idle
        targetRadius = 0.35 + breathe + 0.12 * math.sin(animationValue * 2 * math.pi + i);
      } else {
        // Idle: slow, calm motion
        targetSpeed = particle.speed * 0.002;
        targetRadius = 0.25 + breathe + 0.05 * math.sin(animationValue * 2 * math.pi + i);
      }
      
      // Smooth acceleration/deceleration (lerp towards target speed)
      final acceleration = 0.05; // Smoothness factor
      particle.currentSpeed += (targetSpeed - particle.currentSpeed) * acceleration;
      
      // Update particle angle with current speed
      particle.angle += particle.currentSpeed;
      
      // Smooth radius transition
      particle.radius += (targetRadius - particle.radius) * 0.05;

      // Calculate position
      final r = particle.radius * maxRadius;
      final x = center.dx + r * math.cos(particle.angle);
      final y = center.dy + r * math.sin(particle.angle);
      final position = Offset(x, y);

      // Draw subtle connections to very close particles
      if (!isProcessing) {
        final linePaint = Paint()
          ..strokeWidth = 0.5
          ..style = PaintingStyle.stroke;
          
        for (var j = i + 1; j < particles.length; j++) {
          final other = particles[j];
          final otherR = other.radius * maxRadius;
          final otherX = center.dx + otherR * math.cos(other.angle);
          final otherY = center.dy + otherR * math.sin(other.angle);
          final otherPos = Offset(otherX, otherY);

          final dist = (position - otherPos).distance;
          if (dist < 50) {
            linePaint.color = particle.color.withValues(alpha: (1 - dist / 50) * 0.15);
            canvas.drawLine(position, otherPos, linePaint);
          }
        }
      }

      // Draw particle with soft glow
      final paint = Paint()
        ..color = particle.color.withValues(alpha: particle.opacity)
        ..style = PaintingStyle.fill;
      
      // Soft glow around particle
      canvas.drawCircle(
        position, 
        particle.size * 2.5, 
        Paint()
          ..color = Colors.white.withValues(alpha: 0.08)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5)
      );

      canvas.drawCircle(position, particle.size, paint);
    }
    
    // Draw gentle central pulse if processing
    if (isProcessing) {
      final pulse = 15 + 5 * math.sin(animationValue * 4 * math.pi);
      canvas.drawCircle(
        center, 
        pulse, 
        Paint()
          ..color = Colors.white.withValues(alpha: 0.2)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8)
      );
      canvas.drawCircle(
        center, 
        8, 
        Paint()..color = Colors.white.withValues(alpha: 0.6)
      );
    }
  }

  @override
  bool shouldRepaint(covariant _NeuralPainter oldDelegate) => true;
}
