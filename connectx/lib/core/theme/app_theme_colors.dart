import 'package:flutter/material.dart';

/// BuildContext extension that provides semantic, theme-aware colours.
extension AppThemeColors on BuildContext {
  bool get _isDark => Theme.of(this).brightness == Brightness.dark;

  // ── Text ──────────────────────────────────────────────────────────────
  /// Primary text / icon — slate-100 (dark) or slate-900 (light)
  Color get appPrimaryColor =>
      _isDark ? const Color(0xFFF1F5F9) : const Color(0xFF0F172A);

  /// Secondary text — slate-400 (dark) or slate-600 (light)
  Color get appSecondaryColor =>
      _isDark ? const Color(0xFF94A3B8) : const Color(0xFF475569);

  /// Hint / muted text — slate-500 (dark) or slate-400 (light)
  Color get appHintColor =>
      _isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8);

  // ── Surfaces ──────────────────────────────────────────────────────────
  /// Card / panel background
  Color get appSurface1 =>
      _isDark ? const Color(0xFF161829) : Colors.white;

  /// Subtle fill / input / secondary background
  Color get appSurface2 =>
      _isDark ? const Color(0xFF1E2235) : const Color(0xFFF1F5F9);

  /// Active chip / badge / pressed-state fill
  Color get appSurface3 =>
      _isDark ? const Color(0xFF252A42) : const Color(0xFFE2E8F0);

  // ── Dividers ──────────────────────────────────────────────────────────
  Color get appDivider =>
      _isDark ? const Color(0xFF1E2235) : const Color(0xFFE2E8F0);

  Color get appDividerLight =>
      _isDark ? const Color(0xFF181B2C) : const Color(0xFFF1F5F9);

  // ── Brand accent ──────────────────────────────────────────────────────
  /// Indigo-500 — consistent across light and dark
  Color get appAccent => const Color(0xFF6366F1);

  // ── Background gradient ───────────────────────────────────────────────
  List<Color> get appGradientColors => _isDark
      ? const [Color(0xFF1A1D35), Color(0xFF0D0F1A)]
      : const [Color(0xFFEEF0FF), Color(0xFFF8F9FF)];
}
