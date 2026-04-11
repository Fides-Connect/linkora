import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_signin_button/flutter_signin_button.dart';
import 'package:provider/provider.dart';

import '../../../../core/providers/user_provider.dart';
import '../../../../core/theme/app_theme_colors.dart';
import '../../../../theme.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../main.dart';

class StartPage extends StatelessWidget {
  const StartPage({super.key});

  Future<void> _onGoogleSignInPressed(BuildContext context) async {
    final userProvider = Provider.of<UserProvider>(context, listen: false);
    try {
      await userProvider.signInWithGoogle();
    } catch (e) {
      // Error is stored in provider, ui updates automatically via Consumer
    }
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    final screenHeight = MediaQuery.of(context).size.height;
    final logoTextGap = (screenHeight * 0.08).clamp(10.0, 80.0).toDouble();

    return Theme(
      data: appTheme,
      child: Scaffold(
        backgroundColor: appTheme.scaffoldBackgroundColor,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: _LanguageToggle(
                currentLocale: Localizations.localeOf(context),
                onSelect: (locale) => ConnectXApp.setLocale(context, locale),
              ),
            ),
          ],
        ),
        body: Stack(
          children: [
            const AppBackground(),
            SafeArea(
              child: Center(
                child: Consumer<UserProvider>(
                    builder: (context, userProvider, _) {
                        return SingleChildScrollView(
                          padding: const EdgeInsets.all(24.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                localizations?.welcomeTitle ?? 'Welcome to ConnectX',
                                style: const TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                localizations?.welcomeMessage ?? 'Sign in to start communicating with the AI assistant',
                                textAlign: TextAlign.center,
                                style: const TextStyle(fontSize: 16),
                              ),
                              SizedBox(height: logoTextGap),
                              SizedBox(
                                width: 100,
                                height: 100,
                                child: Image.asset(
                                  'assets/images/LinkoraLogo.png',
                                  fit: BoxFit.contain,
                                  semanticLabel: 'Linkora Logo',
                                ),
                              ),
                              SizedBox(height: logoTextGap),
                              
                              if (userProvider.isLoading)
                                const SizedBox(
                                  width: 220,
                                  height: 48,
                                  child: Center(child: CircularProgressIndicator()),
                                )
                              else ...[
                                // Google Sign-In Button
                                SignInButton(
                                  Buttons.GoogleDark,
                                  onPressed: () => _onGoogleSignInPressed(context),
                                ),
                              ],
                              if (userProvider.error != null) ...[
                                const SizedBox(height: 12),
                                Text(
                                  userProvider.error!,
                                  style: TextStyle(
                                    color: userProvider.error!.contains('Code sent') ? Colors.green : Colors.red,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ],
                          ),
                        );
                    }
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Compact segmented language toggle used on the start screen AppBar.
///
/// Shows two pill-shaped buttons side by side.  The currently active language
/// is highlighted with the primary app color as background and contrasting text
/// (dark on dark themes, light on light themes); the inactive one is
/// transparent with primary-color text.
class _LanguageToggle extends StatelessWidget {
  final Locale currentLocale;
  final ValueChanged<Locale> onSelect;

  const _LanguageToggle({
    required this.currentLocale,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 34,
      decoration: BoxDecoration(
        color: context.appSurface2,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _ToggleButton(
            label: 'EN',
            selected: currentLocale.languageCode == 'en',
            onTap: () => onSelect(const Locale('en', '')),
          ),
          _ToggleButton(
            label: 'DE',
            selected: currentLocale.languageCode == 'de',
            onTap: () => onSelect(const Locale('de', '')),
          ),
        ],
      ),
    );
  }
}

class _ToggleButton extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ToggleButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isSelected = selected;
    return Semantics(
      button: true,
      enabled: !isSelected,
      label: label,
      selected: isSelected,
      child: InkWell(
        onTap: isSelected ? null : onTap,
        borderRadius: BorderRadius.circular(20),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: isSelected ? context.appPrimaryColor : Colors.transparent,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: isSelected
                  ? (Theme.of(context).brightness == Brightness.dark ? Colors.black87 : Colors.white)
                  : context.appPrimaryColor,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}
