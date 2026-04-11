import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Backward-compat alias — still resolves to the dark theme.
final ThemeData appTheme = darkAppTheme;

// ── Brand ──────────────────────────────────────────────────────────────────
const Color _kSeed    = Color(0xFF6366F1); // Indigo-500
const Color _kDarkBg  = Color(0xFF0D0F1A); // Deep navy-black
const Color _kLightBg = Color(0xFFF8F9FF); // Blue-tinted near-white

// ── Typography ─────────────────────────────────────────────────────────────
TextTheme _buildTextTheme({required bool dark}) {
  final base = dark ? const Color(0xFFF1F5F9) : const Color(0xFF0F172A);
  return TextTheme(
    displayLarge:   GoogleFonts.plusJakartaSans(color: base, fontSize: 57, fontWeight: FontWeight.w700),
    displayMedium:  GoogleFonts.plusJakartaSans(color: base, fontSize: 45, fontWeight: FontWeight.w700),
    displaySmall:   GoogleFonts.plusJakartaSans(color: base, fontSize: 36, fontWeight: FontWeight.w600),
    headlineLarge:  GoogleFonts.plusJakartaSans(color: base, fontSize: 32, fontWeight: FontWeight.w600),
    headlineMedium: GoogleFonts.plusJakartaSans(color: base, fontSize: 28, fontWeight: FontWeight.w600),
    headlineSmall:  GoogleFonts.plusJakartaSans(color: base, fontSize: 24, fontWeight: FontWeight.w600),
    titleLarge:     GoogleFonts.plusJakartaSans(color: base, fontSize: 22, fontWeight: FontWeight.w600),
    titleMedium:    GoogleFonts.plusJakartaSans(color: base, fontSize: 16, fontWeight: FontWeight.w500),
    titleSmall:     GoogleFonts.plusJakartaSans(color: base, fontSize: 14, fontWeight: FontWeight.w500),
    bodyLarge:      GoogleFonts.inter(color: base, fontSize: 16, fontWeight: FontWeight.w400),
    bodyMedium:     GoogleFonts.inter(color: base, fontSize: 14, fontWeight: FontWeight.w400),
    bodySmall:      GoogleFonts.inter(color: base, fontSize: 12, fontWeight: FontWeight.w400),
    labelLarge:     GoogleFonts.inter(color: base, fontSize: 14, fontWeight: FontWeight.w600),
    labelMedium:    GoogleFonts.inter(color: base, fontSize: 12, fontWeight: FontWeight.w600),
    labelSmall:     GoogleFonts.inter(color: base, fontSize: 11, fontWeight: FontWeight.w500),
  );
}

// ── Dark Theme ─────────────────────────────────────────────────────────────
final ThemeData darkAppTheme = ThemeData(
  colorScheme: ColorScheme.fromSeed(
    seedColor: _kSeed,
    brightness: Brightness.dark,
    surface: const Color(0xFF161829),
    onSurface: const Color(0xFFF1F5F9),
  ),
  useMaterial3: true,
  scaffoldBackgroundColor: _kDarkBg,
  textTheme: _buildTextTheme(dark: true),
  cardTheme: CardThemeData(
    color: const Color(0xFF161829),
    elevation: 0,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
  ),
  dividerTheme: const DividerThemeData(color: Color(0xFF1E2235), thickness: 1, space: 1),
  switchTheme: SwitchThemeData(
    thumbColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? Colors.white : const Color(0xFF94A3B8)),
    trackColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? _kSeed : const Color(0xFF1E2235)),
  ),
);

// ── Light Theme ────────────────────────────────────────────────────────────
final ThemeData lightAppTheme = ThemeData(
  colorScheme: ColorScheme.fromSeed(
    seedColor: _kSeed,
    brightness: Brightness.light,
    surface: Colors.white,
    onSurface: const Color(0xFF0F172A),
  ),
  useMaterial3: true,
  scaffoldBackgroundColor: _kLightBg,
  textTheme: _buildTextTheme(dark: false),
  cardTheme: CardThemeData(
    color: Colors.white,
    elevation: 0,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
  ),
  dividerTheme: const DividerThemeData(color: Color(0xFFE2E8F0), thickness: 1, space: 1),
  switchTheme: SwitchThemeData(
    thumbColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? Colors.white : const Color(0xFF94A3B8)),
    trackColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? _kSeed : const Color(0xFFE2E8F0)),
  ),
);