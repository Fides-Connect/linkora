import 'package:flutter/material.dart';

import '../theme/app_theme_colors.dart';

/// Full-screen background. Dark mode adds a subtle radial indigo glow at top.
class AppBackground extends StatelessWidget {
  const AppBackground({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gradientColors = context.appGradientColors;
    return Stack(
      fit: StackFit.expand,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: gradientColors,
            ),
          ),
        ),
        if (isDark)
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: const Alignment(0, -0.55),
                radius: 0.9,
                colors: [
                  const Color(0xFF6366F1).withValues(alpha: 0.09),
                  Colors.transparent,
                ],
              ),
            ),
          ),
      ],
    );
  }
}