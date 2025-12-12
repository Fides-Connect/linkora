import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'firebase_options.dart';
import 'widgets/ai_blob_visualizer.dart';
import 'services/speech_service.dart';
import 'services/auth_service.dart';
import 'services/notification_service.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:async';
import 'pages/start_page.dart';
import 'theme.dart';
import 'widgets/app_background.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'widgets/auth_guard.dart';
import 'localization/app_localizations.dart';

/// Conversation state enum
enum ConversationState {
  idle,       // Not connected
  listening,  // Connected and listening to user
  processing, // Processing user input (thinking)
}

/// Background message handler - must be top-level function
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  debugPrint('Background message received: ${message.messageId}');
  debugPrint('Title: ${message.notification?.title}');
  debugPrint('Body: ${message.notification?.body}');
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(); // Load environment variables from .env file

  // Initialize Firebase with generated options
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  // Set up background message handler
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

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
      home: StreamBuilder<User?>(
        stream: widget.auth.onCurrentUserChanged,
        initialData: widget.auth.currentUser,
        builder: (context, snapshot) {
          // Log the connection state and data
          debugPrint('Auth StreamBuilder - ConnectionState: ${snapshot.connectionState}, HasData: ${snapshot.hasData}, User: ${snapshot.data?.email}');
          
          // Wait for the stream to be ready
          if (snapshot.connectionState == ConnectionState.waiting && snapshot.data == null) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          
          final user = snapshot.data;
          if (user != null) {
            debugPrint('User is signed in: ${user.email}');
            return const ConnectXHomePage();
          } else {
            debugPrint('No user signed in, showing StartPage');
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
  User? _user;

  StreamSubscription<User?>? _userSub;

  ConversationState _conversationState = ConversationState.idle;
  String _currentMessage = '';
  String _statusText = '';
  bool _isInitialized = false;
  final List<String> _topics = [
    'Preferred role',
    'Location radius',
    'Salary band',
    'Workstyle flexibility',
    'Seniority expectations',
  ];

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

  void _setupForegroundMessageHandler() {
    // Handle foreground messages
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      debugPrint('Foreground message received: ${message.messageId}');
      debugPrint('Title: ${message.notification?.title}');
      debugPrint('Body: ${message.notification?.body}');
      
      // Show notification using NotificationService
      if (message.notification != null) {
        final notification = message.notification!;
        // Use message hashCode as notification ID to ensure uniqueness
        final notificationId = message.messageId?.hashCode ?? DateTime.now().millisecondsSinceEpoch;
        NotificationService().showNotification(
          id: notificationId,
          title: notification.title ?? 'New Message',
          body: notification.body ?? '',
        );
      }
    });

    // Handle notification taps when app is in foreground or background
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      debugPrint('Notification opened from background: ${message.messageId}');
      // Handle navigation or custom action when user taps notification
      if (message.data.isNotEmpty) {
        debugPrint('Message data: ${message.data}');
        // You can navigate to specific screens based on message.data
      }
    });
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

    // Set up FCM foreground message handler
    _setupForegroundMessageHandler();

    // Set up speech service callbacks
    _speechService.onSpeechStart = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _conversationState = ConversationState.listening;
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
        _conversationState = ConversationState.idle;
        _statusText = localizations?.disconnected ?? 'Disconnected';
      });
    };

    _speechService.onDisconnected = () {
      final localizations = AppLocalizations.of(context);
      setState(() {
        _conversationState = ConversationState.idle;
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
        _conversationState = ConversationState.idle;
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
      _conversationState = ConversationState.idle;
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

            // User avatar and logout button (top-right)
            Positioned(
              top: 20,
              right: 20,
              child: _user != null
                  ? Row(
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
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        IconButton(
                          icon: const Icon(Icons.logout),
                          onPressed: () async {
                            await _auth.signOut();
                          },
                        ),
                      ],
                    )
                  : const SizedBox.shrink(),
            ),

            // Main content with stage + headline
            Column(
              children: [
                const SizedBox(height: 48),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Row(
                    children: const [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Atlas - AI job agent',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 22,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.2,
                              ),
                            ),
                            SizedBox(height: 6),
                            Text(
                              'Speak your needs. See intent visualized.',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                                fontWeight: FontWeight.w400,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 26),
                Expanded(
                  child: Center(
                    child: AIBlobVisualizer(
                      isListening: _conversationState == ConversationState.listening,
                      isProcessing: _conversationState == ConversationState.processing,
                      size: 260,
                      primaryColor: const Color(0xFF5EEAD4),
                      secondaryColor: const Color(0xFF6366F1),
                      accentColor: const Color(0xFF93C5FD),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),

            // Speech-first glass card with two-line chat + topics
            Positioned(
              left: 16,
              right: 16,
              bottom: 132,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.25),
                      blurRadius: 20,
                      offset: const Offset(0, 12),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            color: _conversationState == ConversationState.processing
                                ? const Color(0xFF22D3EE)
                                : const Color(0xFF86EFAC),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _conversationState == ConversationState.listening
                              ? 'Live listening'
                              : _conversationState == ConversationState.processing
                                  ? 'Thinking with Atlas'
                                  : 'Ready for your voice',
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _currentMessage.isNotEmpty ? _currentMessage : _statusText,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 8,
                      children: _topics
                          .map(
                            (topic) => Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 6,
                                  height: 6,
                                  margin: const EdgeInsets.only(right: 6),
                                  decoration: const BoxDecoration(
                                    color: Colors.white70,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                Text(
                                  topic,
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),

            // Bottom microphone button (center, single button)
            Positioned(
              bottom: 40,
              left: 0,
              right: 0,
              child: Center(
                child: GestureDetector(
                  onTap: _conversationState != ConversationState.idle ? _stopChat : _startChat,
                  child: Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _conversationState != ConversationState.idle
                          ? Colors.red.withValues(alpha: 0.8)
                          : const Color(0xFF6C63FF),
                      boxShadow: [
                        BoxShadow(
                          color: (_conversationState != ConversationState.idle
                              ? Colors.red 
                              : const Color(0xFF6C63FF))
                              .withValues(alpha: 0.3),
                          blurRadius: 20,
                          spreadRadius: 5,
                        ),
                      ],
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.2),
                        width: 1.5,
                      ),
                    ),
                    child: Icon(
                      _conversationState != ConversationState.idle ? Icons.mic_off : Icons.mic,
                      color: Colors.white,
                      size: 32,
                    ),
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
