import 'package:flutter/material.dart';

/// Application-wide constants
class AppConstants {
  // Private constructor to prevent instantiation
  AppConstants._();

  // Colors
  static const Color primaryCyan = Color(0xFF22D3EE);
  static const Color primaryPurple = Color(0xFF6366F1);
  static const Color accentPurple = Color(0xFF818CF8);

  // Sizes
  static const double micButtonSize = 80.0;
  static const double micIconSize = 36.0;
  static const double neuralVisualizerSize = 300.0;
  static const double chatDisplayHeight = 380.0;

  // Animation durations
  static const Duration neuralAnimationDuration = Duration(seconds: 4);
  static const Duration defaultTransitionDuration = Duration(milliseconds: 300);

  // Neural Visualizer
  static const int particleCount = 30;

  // Default topics (can be fetched from backend in future)
  static const List<String> defaultTopics = [
    'Salary Expectations',
    'Remote Work',
    'Experience Level',
    'Relocation',
  ];

  // Spacing
  static const double defaultPadding = 32.0;
  static const double smallPadding = 20.0;
  static const double largePadding = 40.0;

  // Shadow
  static const double shadowBlurRadius = 30.0;
  static const double shadowSpreadRadius = 5.0;
  static const double shadowOpacity = 0.4;
}
