import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_signin_button/flutter_signin_button.dart';

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

  @override
  void initState() {
    super.initState();
    // Initialize AuthService
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

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _onGoogleSignInPressed() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      await _auth.signInWithGoogle();
    } catch (e) {
      setState(() => _error = 'Sign-in failed: $e');
    } finally {
      setState(() => _loading = false);
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
                child: SingleChildScrollView(
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
                      if (!_initialized)
                        const SizedBox(
                          width: 220,
                          height: 48,
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else ...[
                        // Google Sign-In Button
                        SignInButton(
                          Buttons.GoogleDark,
                          onPressed: _loading ? null : _onGoogleSignInPressed,
                        ),
                      ],
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          _error!,
                          style: TextStyle(
                            color: _error!.contains('Code sent') ? Colors.green : Colors.red,
                          ),
                          textAlign: TextAlign.center,
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
