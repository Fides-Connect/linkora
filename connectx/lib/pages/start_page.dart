import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:google_sign_in_web/web_only.dart' as web_render;

import '../services/auth_service.dart';

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
    // Initialize the GoogleSignIn singleton; pass clientId from env if present.
    _auth
        .initialize()
        .then((_) {
      if (!mounted) return;
      setState(() {
        _initialized = true;
      });

      // On web, listen for authentication events and navigate when signed in
      if (kIsWeb) {
        GoogleSignIn.instance.authenticationEvents.listen((event) {
          if (event is GoogleSignInAuthenticationEventSignIn) {
            if (mounted) Navigator.pushReplacementNamed(context, '/home');
          }
        });
      }
    }).catchError((e) {
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
      Navigator.pushReplacementNamed(context, '/home');
    } catch (e) {
      setState(() => _error = 'Sign-in failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Welcome to Fides', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                const SizedBox(height: 20),
                if (kIsWeb) ...[
                  // Use the web plugin's renderButton which returns a Widget
                  if (!_initialized)
                    const SizedBox(width: 220, height: 48, child: Center(child: CircularProgressIndicator()))
                  else
                    SizedBox(
                      width: 220,
                      height: 48,
                      child: web_render.renderButton(),
                    ),
                ] else ...[
                  ElevatedButton.icon(
                    onPressed: _loading ? null : _onSignInPressed,
                    icon: const Icon(Icons.login),
                    label: Text(_loading ? 'Signing in…' : 'Sign in with Google'),
                    style: ElevatedButton.styleFrom(minimumSize: const Size(220, 48), backgroundColor: const Color(0xFF6C63FF)),
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ]
              ],
            ),
          ),
        ),
      ),
    );
  }
}
