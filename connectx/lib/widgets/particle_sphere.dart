import 'dart:math' as math;
import 'package:flutter/material.dart';

class Particle {
  double x, y, z;
  double vx, vy, vz;
  double size;
  Color color;
  
  Particle({
    required this.x,
    required this.y,
    required this.z,
    required this.vx,
    required this.vy,
    required this.vz,
    required this.size,
    required this.color,
  });
}

class ParticleSphere extends StatefulWidget {
  final bool isAnimating;
  final double radius;
  final int particleCount;
  final Color primaryColor;
  final Color secondaryColor;
  
  const ParticleSphere({
    super.key,
    this.isAnimating = false,
    this.radius = 120.0,
    this.particleCount = 100,
    this.primaryColor = Colors.blue,
    this.secondaryColor = Colors.cyan,
  });

  @override
  State<ParticleSphere> createState() => _ParticleSphereState();
}

class _ParticleSphereState extends State<ParticleSphere>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  List<Particle> particles = [];
  double rotationX = 0;
  double rotationY = 0;
  
  @override
  void initState() {
    super.initState();
    
    // Main animation controller for particle movement
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 16), // ~60 FPS
      vsync: this,
    );
    
    // Pulse animation controller for TTS response
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    
    _pulseAnimation = Tween<double>(
      begin: 1.0,
      end: 1.3,
    ).animate(CurvedAnimation(
      parent: _pulseController,
      curve: Curves.easeInOut,
    ));
    
    _initializeParticles();
    _startAnimation();
  }
  
  void _initializeParticles() {
    particles.clear();
    final random = math.Random();
    
    for (int i = 0; i < widget.particleCount; i++) {
      // Generate points on a sphere surface
      final theta = random.nextDouble() * 2 * math.pi;
      final phi = math.acos(2 * random.nextDouble() - 1);
      
      final x = widget.radius * math.sin(phi) * math.cos(theta);
      final y = widget.radius * math.sin(phi) * math.sin(theta);
      final z = widget.radius * math.cos(phi);
      
      // Random velocity for floating effect
      final vx = (random.nextDouble() - 0.5) * 0.5;
      final vy = (random.nextDouble() - 0.5) * 0.5;
      final vz = (random.nextDouble() - 0.5) * 0.5;
      
      final size = 2.0 + random.nextDouble() * 4.0;
      final colorT = random.nextDouble();
      final color = Color.lerp(widget.primaryColor, widget.secondaryColor, colorT)!;
      
      particles.add(Particle(
        x: x,
        y: y,
        z: z,
        vx: vx,
        vy: vy,
        vz: vz,
        size: size,
        color: color,
      ));
    }
  }
  
  void _startAnimation() {
    _animationController.addListener(() {
      _updateParticles();
      setState(() {});
    });
    
    if (widget.isAnimating) {
      _animationController.repeat();
      _pulseController.repeat(reverse: true);
    }
  }
  
  void _updateParticles() {
    rotationX += 0.01;
    rotationY += 0.005;
    
    if (widget.isAnimating) {
      for (var particle in particles) {
        // Add some floating motion
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.z += particle.vz;
        
        // Keep particles roughly in sphere shape with elastic effect
        final distance = math.sqrt(particle.x * particle.x + 
                                  particle.y * particle.y + 
                                  particle.z * particle.z);
        
        if (distance > widget.radius * 1.2) {
          particle.vx *= -0.8;
          particle.vy *= -0.8;
          particle.vz *= -0.8;
        }
        
        // Add slight attraction back to sphere surface
        final targetDistance = widget.radius;
        if (distance > 0) {
          final factor = 0.02;
          particle.vx += (particle.x / distance) * (targetDistance - distance) * factor;
          particle.vy += (particle.y / distance) * (targetDistance - distance) * factor;
          particle.vz += (particle.z / distance) * (targetDistance - distance) * factor;
        }
        
        // Damping
        particle.vx *= 0.99;
        particle.vy *= 0.99;
        particle.vz *= 0.99;
      }
    }
  }
  
  @override
  void didUpdateWidget(ParticleSphere oldWidget) {
    super.didUpdateWidget(oldWidget);
    
    if (widget.isAnimating != oldWidget.isAnimating) {
      if (widget.isAnimating) {
        _animationController.repeat();
        _pulseController.repeat(reverse: true);
      } else {
        _animationController.stop();
        _pulseController.stop();
        _pulseController.reset();
      }
    }
  }
  
  @override
  void dispose() {
    _animationController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulseAnimation,
      child: CustomPaint(
        size: Size(widget.radius * 2.5, widget.radius * 2.5),
        painter: ParticleSpherePainter(
          particles: particles,
          rotationX: rotationX,
          rotationY: rotationY,
          isAnimating: widget.isAnimating,
        ),
      ),
      builder: (context, child) {
        return Transform.scale(
          scale: widget.isAnimating ? _pulseAnimation.value : 1.0,
          child: child,
        );
      },
    );
  }
}

class ParticleSpherePainter extends CustomPainter {
  final List<Particle> particles;
  final double rotationX;
  final double rotationY;
  final bool isAnimating;
  
  ParticleSpherePainter({
    required this.particles,
    required this.rotationX,
    required this.rotationY,
    required this.isAnimating,
  });
  
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    
    // Sort particles by z-depth for proper rendering
    final sortedParticles = List<Particle>.from(particles);
    sortedParticles.sort((a, b) => b.z.compareTo(a.z));
    
    for (final particle in sortedParticles) {
      // Apply 3D rotation
      final rotatedX = particle.x * math.cos(rotationY) - particle.z * math.sin(rotationY);
      final rotatedZ = particle.x * math.sin(rotationY) + particle.z * math.cos(rotationY);
      final rotatedY = particle.y * math.cos(rotationX) - rotatedZ * math.sin(rotationX);
      final finalZ = particle.y * math.sin(rotationX) + rotatedZ * math.cos(rotationX);
      
      // Project 3D to 2D
      final perspective = 1000.0;
      final projectedX = rotatedX * perspective / (perspective + finalZ);
      final projectedY = rotatedY * perspective / (perspective + finalZ);
      
      // Calculate depth-based opacity and size
      final depth = (finalZ + 200) / 400;
      final opacity = (depth * 0.8 + 0.2).clamp(0.0, 1.0);
      final adjustedSize = particle.size * (depth * 0.5 + 0.5);
      
      final paint = Paint()
        ..color = particle.color.withValues(alpha: opacity)
        ..style = PaintingStyle.fill;
      
      // Add glow effect when animating
      if (isAnimating) {
        final glowPaint = Paint()
          ..color = particle.color.withValues(alpha: opacity * 0.3)
          ..style = PaintingStyle.fill
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3.0);
        
        canvas.drawCircle(
          center + Offset(projectedX, projectedY),
          adjustedSize * 2,
          glowPaint,
        );
      }
      
      canvas.drawCircle(
        center + Offset(projectedX, projectedY),
        adjustedSize,
        paint,
      );
    }
  }
  
  @override
  bool shouldRepaint(ParticleSpherePainter oldDelegate) {
    return true; // Always repaint for smooth animation
  }
}