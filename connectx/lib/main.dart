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
import 'package:flutter/foundation.dart' show kIsWeb;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(); // Load environment variables from .env file

  // Initialize Google Sign-In early (important for web plugin)
  try {
    await AuthService().initialize();
    // Try to restore a previous sign-in before the UI builds so the main
    // screen can read `AuthService.currentUser` immediately.
    try {
      // await AuthService().signInSilently();
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
    debugPrint('AuthGate: current user = $_user');
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
    // Automatically start the microphone when app loads
    // WidgetsBinding.instance.addPostFrameCallback((_) {
    //   _startChat();
    // });
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
    debugPrint('Building ConnectXHomePage with user: $_user');
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
                            // Right-aligned user controls
                            if (_user != null)
                              Align(
                                alignment: Alignment.centerRight,
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    // User avatar if not web and photoUrl is available
                                    // On web, just show initials due to CORS issues
                                    if (_auth.photoUrl != null && _auth.photoUrl!.isNotEmpty && !kIsWeb)
                                      ClipOval(
                                        child: Image.network(
                                          _auth.photoUrl!,
                                          width: 32,
                                          height: 32,
                                          fit: BoxFit.cover,
                                        ),
                                      )
                                    else
                                      CircleAvatar(
                                        radius: 16,
                                        backgroundColor: const Color(0xFF6C63FF),
                                        child: Text(
                                          // derive initials from display name if possible
                                          (_user?.displayName ?? '')
                                              .split(' ')
                                              .where((s) => s.isNotEmpty)
                                              .map((s) => s[0])
                                              .take(2)
                                              .join()
                                              .toUpperCase(),
                                          style: const TextStyle(color: Colors.white, fontSize: 12),
                                        ),
                                      ),
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
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      // Centered title
                      Center(
                        child: Text(
                          'Fides',
                          style: Theme.of(context).textTheme.headlineMedium
                              ?.copyWith(
                                color: const Color(0xFF6C63FF),
                                fontWeight: FontWeight.bold,
                              ),
                          textAlign: TextAlign.center,
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
