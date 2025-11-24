import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_signin_button/flutter_signin_button.dart';
import 'package:firebase_auth/firebase_auth.dart';

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

enum AuthMode { signIn, signUp }

class _StartPageState extends State<StartPage> {
  final AuthService _auth = AuthService();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  
  bool _loading = false;
  bool _initialized = false;
  String? _error;
  AuthMode _authMode = AuthMode.signIn;
  bool _showEmailForm = false;

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
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _onGoogleSignInPressed() async {
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

  Future<void> _onEmailAuthPressed() async {
    if (_emailController.text.isEmpty || _passwordController.text.isEmpty) {
      setState(() => _error = 'Please enter email and password');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      if (_authMode == AuthMode.signUp) {
        await _auth.createUserWithEmail(
          _emailController.text.trim(),
          _passwordController.text,
        );
      } else {
        await _auth.signInWithEmail(
          _emailController.text.trim(),
          _passwordController.text,
        );
      }
    } on FirebaseAuthException catch (e) {
      setState(() {
        switch (e.code) {
          case 'user-not-found':
            _error = 'No user found with this email';
            break;
          case 'wrong-password':
            _error = 'Wrong password';
            break;
          case 'email-already-in-use':
            _error = 'Email already in use';
            break;
          case 'weak-password':
            _error = 'Password is too weak';
            break;
          case 'invalid-email':
            _error = 'Invalid email address';
            break;
          default:
            _error = 'Authentication failed: ${e.message}';
        }
      });
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
                      else ...[
                        // Google Sign-In Button
                        SignInButton(
                          Buttons.GoogleDark,
                          onPressed: _loading ? null : _onGoogleSignInPressed,
                        ),
                        const SizedBox(height: 16),
                        const Text('OR', style: TextStyle(fontSize: 14)),
                        const SizedBox(height: 16),
                        
                        // Email/Password Sign In Option
                        if (!_showEmailForm)
                          OutlinedButton.icon(
                            onPressed: () => setState(() => _showEmailForm = true),
                            icon: const Icon(Icons.email),
                            label: const Text('Sign in with Email'),
                          ),
                        
                        // Email/Password Form
                        if (_showEmailForm) ...[
                          ToggleButtons(
                            isSelected: [_authMode == AuthMode.signIn, _authMode == AuthMode.signUp],
                            onPressed: (index) {
                              setState(() {
                                _authMode = index == 0 ? AuthMode.signIn : AuthMode.signUp;
                              });
                            },
                            children: const [
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 16),
                                child: Text('Sign In'),
                              ),
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 16),
                                child: Text('Sign Up'),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          TextField(
                            controller: _emailController,
                            decoration: const InputDecoration(
                              labelText: 'Email',
                              border: OutlineInputBorder(),
                              filled: true,
                            ),
                            keyboardType: TextInputType.emailAddress,
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _passwordController,
                            decoration: const InputDecoration(
                              labelText: 'Password',
                              border: OutlineInputBorder(),
                              filled: true,
                            ),
                            obscureText: true,
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _loading ? null : _onEmailAuthPressed,
                            child: Text(_authMode == AuthMode.signIn ? 'Sign In' : 'Sign Up'),
                          ),
                          TextButton(
                            onPressed: () => setState(() => _showEmailForm = false),
                            child: const Text('Cancel'),
                          ),
                        ],
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
