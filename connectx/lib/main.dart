import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'widgets/particle_sphere.dart';
import 'services/speech_service.dart';
import 'services/auth_service.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'dart:async';
import 'pages/start_page.dart';
import 'theme.dart';
import 'widgets/app_background.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(); // Load environment variables from .env file

  // Initialize Google Sign-In early (important for web plugin)
  try {
    await AuthService().initialize();
    // Try to restore a previous sign-in before the UI builds so the main
    // screen can read `AuthService.currentUser` immediately.
    try {
      await AuthService().signInSilently();
    } catch (_) {}
  } catch (_) {}

  runApp(const ConnectXApp());
}

class ConnectXApp extends StatelessWidget {
  const ConnectXApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ConnectX',
      theme: appTheme,
      initialRoute: '/',
      routes: {
        '/': (context) => const StartPage(),
        '/home': (context) => AuthGate(child: const ConnectXHomePage()),
      },
      debugShowCheckedModeBanner: false,
    );
  }
}

/// Simple gate that shows [child] only when a user is signed in, otherwise
/// forwards to the `StartPage`.
class AuthGate extends StatefulWidget {
  final Widget child;
  const AuthGate({required this.child, super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final AuthService _auth = AuthService();
  GoogleSignInAccount? _user;
  StreamSubscription<GoogleSignInAccount?>? _sub;
  bool _redirectScheduled = false;

  @override
  void initState() {
    super.initState();
    _user = _auth.currentUser;
    _sub = _auth.onCurrentUserChanged.listen((u) => setState(() => _user = u));
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // If user is signed in, show the guarded child.
    if (_user != null) return widget.child;

    // Otherwise actively redirect to the StartPage so the URL updates and
    // the navigation stack is changed. Use a post-frame callback to avoid
    // calling Navigator during build and guard to schedule the redirect only once.
    if (!_redirectScheduled) {
      _redirectScheduled = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
      });
    }

    // While redirecting, render an empty placeholder.
    return const SizedBox.shrink();
  }
}

class ConnectXHomePage extends StatefulWidget {
  const ConnectXHomePage({super.key});

  @override
  State<ConnectXHomePage> createState() => _ConnectXHomePageState();
}

class _ConnectXHomePageState extends State<ConnectXHomePage> {
  late SpeechService _speechService;
  final AuthService _auth = AuthService();
  GoogleSignInAccount? _user;

  StreamSubscription<GoogleSignInAccount?>? _userSub;

  bool _isAnimating = false;
  bool _isChatting = false;
  String _currentMessage = '';
  String _statusText = 'Tap the microphone to start speaking';

  @override
  void initState() {
    super.initState();
    _initializeServices();
  }

  void _initializeServices() {
    _speechService = SpeechService();

    // Subscribe to auth changes
    _user = _auth.currentUser;
    _userSub = _auth.onCurrentUserChanged.listen((u) {
      setState(() => _user = u);
    });

    // Set up speech service callbacks
    _speechService.onSpeechStart = () {
      setState(() {
        _isChatting = true;
        _isAnimating = true;
        _statusText = 'Connecting to AI-Assistant...';
      });
    };

    _speechService.onConnected = () {
      setState(() {
        _statusText = 'Connected! AI is listening and responding...';
      });
    };

    _speechService.onSpeechEnd = () {
      setState(() {
        _isChatting = false;
        _isAnimating = false;
        _statusText = 'Disconnected';
      });
    };

    _speechService.onDisconnected = () {
      setState(() {
        _isChatting = false;
        _isAnimating = false;
        _statusText = 'Connection closed';
      });
    };

    // end _initializeServices
  }

  @override
  void dispose() {
    _userSub?.cancel();
    super.dispose();
  }

  void _startChat() async {
    try {
      await _speechService.startSpeech();
    } catch (e) {
      setState(() {
        _statusText = 'Error: ${e.toString()}';
        _isChatting = false;
        _isAnimating = false;
      });
    }
  }

  Future<void> _stopChat() async {
    // Provide haptic feedback
    HapticFeedback.mediumImpact();
    try {
      _speechService.stopSpeech();
    } catch (e) {
      print('Error stopping chat: $e');
    }

    setState(() {
      _isChatting = false;
      _isAnimating = false;
      _currentMessage = '';
      _statusText = 'Chat stopped. Tap the microphone to start again.';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            // Background gradient
            const AppBackground(),

            // Main content
            Column(
              children: [
                // Status bar
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      SizedBox(
                        height: 44,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            // Centered title
                            Center(
                              child: Text(
                                'Fides',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineMedium
                                    ?.copyWith(
                                      color: const Color(0xFF6C63FF),
                                      fontWeight: FontWeight.bold,
                                    ),
                                textAlign: TextAlign.center,
                              ),
                            ),

                            // Right-aligned user controls
                            if (_user != null)
                              Align(
                                alignment: Alignment.centerRight,
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    CircleAvatar(
                                      backgroundImage: _user!.photoUrl != null
                                          ? NetworkImage(_user!.photoUrl!)
                                          : null,
                                      radius: 16,
                                      child: _user!.photoUrl == null
                                          ? const Icon(Icons.person)
                                          : null,
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      _user!.displayName ?? _user!.email,
                                      style: const TextStyle(
                                        color: Colors.white70,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    TextButton(
                                      onPressed: () async {
                                        final navigator = Navigator.of(context);
                                        await _auth.signOut();
                                        if (!mounted) return;
                                        navigator.pushNamedAndRemoveUntil(
                                          '/',
                                          (route) => false,
                                        );
                                      },
                                      child: const Text('Sign out'),
                                    ),
                                    const SizedBox(width: 8),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        _statusText,
                        style: Theme.of(
                          context,
                        ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),

                // Particle sphere in the center
                Expanded(
                  child: Center(
                    child: ParticleSphere(
                      isAnimating: _isAnimating,
                      radius: 120,
                      particleCount: 80,
                      primaryColor: const Color(0xFF6C63FF),
                      secondaryColor: const Color(0xFF00D4FF),
                    ),
                  ),
                ),

                // Current message display
                if (_currentMessage.isNotEmpty)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.all(20),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: const Color(0xFF6C63FF).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      _currentMessage,
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: Colors.white),
                      textAlign: TextAlign.center,
                    ),
                  ),
              ],
            ),

            // Bottom action buttons
            Positioned(
              bottom: 40,
              left: 40,
              child: FloatingActionButton(
                onPressed: _stopChat,
                backgroundColor: Colors.red.withValues(alpha: 0.8),
                heroTag: 'stop_button',
                child: const Icon(Icons.stop, color: Colors.white),
              ),
            ),

            Positioned(
              bottom: 40,
              right: 40,
              child: FloatingActionButton.large(
                onPressed: _isChatting ? null : _startChat,
                backgroundColor: _isChatting
                    ? const Color(0xFF6C63FF).withValues(alpha: 0.5)
                    : const Color(0xFF6C63FF),
                heroTag: 'mic_button',
                child: Icon(
                  _isChatting ? Icons.mic : Icons.mic_none,
                  color: Colors.white,
                  size: 32,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
