import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_signin_button/flutter_signin_button.dart'; // For non-web platforms
import '../widgets/sign_in_button_stub.dart'
    if (dart.library.html) 'package:google_sign_in_web/web_only.dart'; // For web platform

import '../services/auth_service.dart';
import '../theme.dart';
import '../widgets/app_background.dart';
import '../localization/app_localizations.dart';
import '../main.dart';

class StartPage extends StatefulWidget {
  const StartPage({super.key});

  @override
  State<StartPage> createState() => _StartPageState();
}

class _StartPageState extends State<StartPage> {
  final AuthService _auth = AuthService();
  bool _loading = false;
  bool _initialized = false;
  String? _error;

  // Track the authentication events subscription so we can cancel it on dispose.
  StreamSubscription<GoogleSignInAuthenticationEvent>? _authSubscription;

  @override
  void initState() {
    super.initState();
    // Initialize the GoogleSignIn singleton; pass clientId from env if present.
    _auth
        .initialize()
        .then((_) {
          if (!mounted) return;
          setState(() {
            _initialized = true;
          });
        })
        .catchError((e) {
          if (mounted) setState(() => _error = 'Init failed: $e');
        });
  }

  Future<void> _onSignInPressed() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      await _auth.signIn();
    } catch (e) {
      setState(() => _error = 'Sign-in failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    final screenHeight = MediaQuery.of(context).size.height;
    // Use 12% of screen height but keep it within reasonable bounds
    final logoTextGap = (screenHeight * 0.12).clamp(10.0, 250.0).toDouble();

    return Theme(
      data: appTheme,
      child: Scaffold(
        backgroundColor: appTheme.scaffoldBackgroundColor,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          actions: [
            PopupMenuButton<Locale>(
              icon: const Icon(Icons.language),
              tooltip: localizations?.selectLanguage ?? 'Select Language',
              onSelected: (Locale locale) {
                ConnectXApp.setLocale(context, locale);
              },
              itemBuilder: (BuildContext context) => [
                const PopupMenuItem<Locale>(
                  value: Locale('en', ''),
                  child: Text('English'),
                ),
                const PopupMenuItem<Locale>(
                  value: Locale('de', ''),
                  child: Text('Deutsch'),
                ),
              ],
            ),
          ],
        ),
        body: Stack(
          children: [
            const AppBackground(),
            SafeArea(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        localizations?.welcomeTitle ?? 'Welcome to Fides',
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
                        width: 120,
                        height: 120,
                        child: Image.asset(
                            'assets/images/FidesLogo.png',
                            fit: BoxFit.contain,
                            semanticLabel: 'Fides Logo',
                          ),
                      ),
                      SizedBox(height: logoTextGap),
                      if (!_initialized)
                        const SizedBox(
                          width: 220,
                          height: 48,
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else if (kIsWeb)
                        SizedBox(
                          width: 220,
                          height: 48,
                          child: renderButton(configuration: GSIButtonConfiguration(
                            theme: GSIButtonTheme.filledBlack,
                          )),
                        )
                      else
                        SignInButton(
                          Buttons.GoogleDark,
                          onPressed: _loading ? null : _onSignInPressed,
                        ),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          _error!,
                          style: const TextStyle(color: Colors.red),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
