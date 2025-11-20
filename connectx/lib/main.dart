import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'widgets/particle_sphere.dart';
import 'services/speech_service.dart';
import 'services/auth_service.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:async';
import 'pages/start_page.dart';
import 'theme.dart';
import 'widgets/app_background.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'widgets/auth_guard.dart';
import 'localization/app_localizations.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(); // Load environment variables from .env file

  // Create a single AuthService instance and initialize it.
  final auth = AuthService();
  try {
    await auth.initialize();
  } catch (e) {
    debugPrint('Error initializing AuthService: $e');
  }

  runApp(ConnectXApp(auth: auth));
}

class ConnectXApp extends StatefulWidget {
  final AuthService auth;
  const ConnectXApp({required this.auth, super.key});

  @override
  State<ConnectXApp> createState() => _ConnectXAppState();

  static void setLocale(BuildContext context, Locale newLocale) {
    _ConnectXAppState? state =
        context.findAncestorStateOfType<_ConnectXAppState>();
    state?.setLocale(newLocale);
  }
}

class _ConnectXAppState extends State<ConnectXApp> {
  Locale? _locale;

  void setLocale(Locale locale) {
    setState(() {
      _locale = locale;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ConnectX',
      theme: appTheme,
      locale: _locale,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [
        Locale('en', ''),
        Locale('de', ''),
      ],
      home: StreamBuilder<GoogleSignInAccount?>(
        stream: widget.auth.onCurrentUserChanged,
        initialData: widget.auth.currentUser,
        builder: (context, snapshot) {
          final user = snapshot.data;
          if (user != null) {
            return const ConnectXHomePage();
          } else {
            return const StartPage();
          }
        },
      ),
      routes: {
        '/start': (context) => const StartPage(),
        '/home': (context) => AuthGuard(
              auth: widget.auth,
              child: const ConnectXHomePage(),
            ),
      },
      debugShowCheckedModeBanner: false,
    );
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
  String _statusText = '';
  bool _isInitialized = false;

  @override
  void initState() {
    super.initState();
    // Request permissions after widget is built and user has signed in
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _requestMicrophonePermission();
      await _requestNotificationPermission();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_isInitialized) {
      _initializeServices();
      _isInitialized = true;
    }
  }

  Future<void> _requestMicrophonePermission() async {
    if (kIsWeb) return;

    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;

    var micStatus = await Permission.microphone.status;

    if (!micStatus.isGranted) {
      // First request
      micStatus = await Permission.microphone.request();

      // If denied, show explanation dialog and ask once more
      if (!micStatus.isGranted && mounted) {
        await showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(localizations.microphonePermissionTitle),
            content: Text(localizations.microphonePermissionMessage),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(localizations.okButton),
              ),
            ],
          ),
        );

        // Ask one more time
        micStatus = await Permission.microphone.request();

        if (!micStatus.isGranted && mounted) {
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(localizations.microphoneAccessDeniedTitle),
              content: Text(localizations.microphoneAccessDeniedMessage),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: Text(localizations.okButton),
                ),
              ],
            ),
          );
        }
      }
    }
  }

  Future<void> _requestNotificationPermission() async {
    if (kIsWeb) return;

    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;

    var notificationStatus = await Permission.notification.status;

    if (!notificationStatus.isGranted) {
      // First request permission
      notificationStatus = await Permission.notification.request();

      // Show explanation dialog if refused
      if (!notificationStatus.isGranted && mounted) {
        await showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(localizations.notificationPermissionTitle),
            content: Text(localizations.notificationPermissionMessage),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(localizations.okButton),
              ),
            ],
          ),
        );
      }
      // Request permission once more
      notificationStatus = await Permission.notification.request();

      // If still denied, show final message
      if (!notificationStatus.isGranted && mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(localizations.notificationAccessDeniedTitle),
            content: Text(localizations.notificationAccessDeniedMessage),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(localizations.okButton),
              ),
            ],
          ),
        );
      }
    }
  }

  void _initializeServices() {
    _speechService = SpeechService();

    // Initialize status text with localization
    final localizations = AppLocalizations.of(context);
    if (localizations != null) {
      _statusText = localizations.tapMicrophoneToStart;
    }

    // Subscribe to auth changes
    _user = _auth.currentUser;
    _userSub = _auth.onCurrentUserChanged.listen((u) {
      setState(() => _user = u);
    });

    // Set up speech service callbacks
    _speechService.onSpeechStart = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _isChatting = true;
        _isAnimating = true;
        _statusText = localizations?.connecting ?? 'Connecting to AI-Assistant...';
      });
    };

    _speechService.onConnected = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _statusText = localizations?.connected ?? 'Connected! AI is listening and responding...';
      });
    };

    _speechService.onSpeechEnd = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _isChatting = false;
        _isAnimating = false;
        _statusText = localizations?.disconnected ?? 'Disconnected';
      });
    };

    _speechService.onDisconnected = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _isChatting = false;
        _isAnimating = false;
        _statusText = localizations?.connectionClosed ?? 'Connection closed';
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
    final localizations = AppLocalizations.of(context);
    try {
      await _speechService.startSpeech();
    } catch (e) {
      final errorMsg = e.toString();
      setState(() {
        _statusText = 'Error: $errorMsg';
        _isChatting = false;
        _isAnimating = false;
      });
      // Show error dialog
      if (mounted && localizations != null) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(localizations.errorTitle),
            content: Text('${localizations.errorOccurred}\n\n$errorMsg'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(localizations.okButton),
              ),
            ],
          ),
        );
      }
    }
  }

  Future<void> _stopChat() async {
    // Provide haptic feedback
    HapticFeedback.mediumImpact();
    try {
      _speechService.stopSpeech();
    } catch (e) {
      debugPrint('Error stopping chat: $e');
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
                                    if (_auth.photoUrl != null &&
                                        _auth.photoUrl!.isNotEmpty &&
                                        !kIsWeb)
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
                                        backgroundColor: const Color(
                                          0xFF6C63FF,
                                        ),
                                        child: Text(
                                          // derive initials from display name if possible
                                          (_user?.displayName ?? '')
                                              .split(' ')
                                              .where((s) => s.isNotEmpty)
                                              .map((s) => s[0])
                                              .take(2)
                                              .join()
                                              .toUpperCase(),
                                          style: const TextStyle(
                                            color: Colors.white,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ),
                                    IconButton(
                                      icon: Icon(Icons.logout),
                                      onPressed: () async {
                                        await _auth.signOut();
                                      },
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
