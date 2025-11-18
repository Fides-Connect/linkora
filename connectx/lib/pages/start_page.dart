import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_signin_button/flutter_signin_button.dart';

import '../widgets/sign_in_button_stub.dart'
    if (dart.library.html) 'package:google_sign_in_web/web_only.dart'
    as sign_in_button_web;
import '../services/auth_service.dart';
import '../theme.dart';
import '../widgets/app_background.dart';

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

          // Listen for authentication events and navigate when signed in
          _authSubscription = GoogleSignIn.instance.authenticationEvents.listen((event) {
            if (event is GoogleSignInAuthenticationEventSignIn) {
              // subscription is cancelled in dispose, so mounted should be true here
              if (mounted) Navigator.pushReplacementNamed(context, '/home');
            }
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
      // Navigate to the voice assistant only on successful sign-in
      if (!mounted) return;
      //Navigator.pushReplacementNamed(context, '/home');
    } catch (e) {
      setState(() => _error = 'Sign-in failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final screenHeight = MediaQuery.of(context).size.height;
    // Use 12% of screen height but keep it within reasonable bounds
    final logoTextGap = (screenHeight * 0.12).clamp(10.0, 250.0).toDouble();

    return Theme(
      data: appTheme,
      child: Scaffold(
        backgroundColor: appTheme.scaffoldBackgroundColor,
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
                      const Text(
                        'Welcome to Fides',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: logoTextGap),
                      SizedBox(
                        width: 120,
                        height: 120,
                        child: GestureDetector(
                          onTap: () {
                            if (!mounted) return;
                            Navigator.pushReplacementNamed(context, '/home');
                          },
                          child: Image.asset(
                            'assets/images/FidesLogo.png',
                            fit: BoxFit.contain,
                            semanticLabel: 'Fides Logo',
                          ),
                        ),
                      ),
                      SizedBox(height: logoTextGap),
                      if (kIsWeb) ...[
                        // Use the web plugin's renderButton which returns a Widget
                        if (!_initialized)
                          const SizedBox(
                            width: 220,
                            height: 48,
                            child: Center(child: CircularProgressIndicator()),
                          )
                        else
                          SizedBox(
                            width: 220,
                            height: 48,
                            child: sign_in_button_web.renderButton(),
                          ),
                      ] else ...[
                        if (!_initialized)
                          const SizedBox(
                            width: 220,
                            height: 48,
                            child: Center(child: CircularProgressIndicator()),
                          )
                        else
                          SignInButton(
                            Buttons.Google,
                            text: _loading
                                ? 'Signing in…'
                                : 'Sign in with Google',
                            onPressed: _loading ? null : _onSignInPressed,
                          ),
                      ],
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
