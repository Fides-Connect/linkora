import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'firebase_options.dart';
import 'widgets/ai_neural_visualizer.dart';
import 'widgets/home/user_header.dart';
import 'widgets/home/topics_list.dart';
import 'widgets/home/chat_display.dart';
import 'widgets/home/mic_button.dart';
import 'utils/permission_helper.dart';
import 'services/speech_service.dart';
import 'services/auth_service.dart';
import 'services/notification_service.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'dart:async';
import 'pages/start_page.dart';
import 'theme.dart';
import 'widgets/app_background.dart';
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
  final List<String> _topics = ['Salary Expectations', 'Remote Work', 'Experience Level', 'Relocation'];
  final List<Map<String, dynamic>> _chatMessages = []; // List of {text: String, isUser: bool}
  String _currentMessage = '';
  String _statusText = '';
  bool _isInitialized = false;

  bool _lastMessageWasUser = false;

  @override
  void initState() {
    super.initState();
    // Request permissions after widget is built and user has signed in
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await PermissionHelper.requestMicrophonePermission(context);
      await PermissionHelper.requestNotificationPermission(context);
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
      setState(() {
        _conversationState = ConversationState.listening;
      });
    };

    _speechService.onConnected = () {
      setState(() {
        // Clear status text so chat messages appear immediately
        _statusText = '';
      });
    };

    _speechService.onSpeechEnd = () {
      setState(() {
        _conversationState = ConversationState.idle;
      });
    };

    _speechService.onDisconnected = () {
      setState(() {
        _conversationState = ConversationState.idle;
      });
    };

    _speechService.onChatMessage = (String text, bool isUser, bool isChunk) {
      setState(() {
        if (isUser) {
          _currentMessage = text;
          _chatMessages.add({'text': text, 'isUser': true});
          _lastMessageWasUser = true;
          _conversationState = ConversationState.processing;
        } else {
          // AI Message
          if (_lastMessageWasUser || _chatMessages.isEmpty || _chatMessages.last['isUser']) {
            // New AI response starting (after user message OR first message OR last was user)
            _currentMessage = text;
            _chatMessages.add({'text': text, 'isUser': false});
            _lastMessageWasUser = false;
            _conversationState = ConversationState.listening; // AI is speaking
          } else {
            // Appending chunks to existing AI response
            _currentMessage += text;
            // Update the last message in the list
            if (_chatMessages.isNotEmpty && !_chatMessages.last['isUser']) {
              _chatMessages.last['text'] = _currentMessage;
            }
          }
        }
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
      _chatMessages.clear();
      // Reset to initial status text
      final localizations = AppLocalizations.of(context);
      if (localizations != null) {
        _statusText = localizations.tapMicrophoneToStart;
      }
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
            UserHeader(user: _user, auth: _auth),

            // Main Layout
            Column(
              children: [
                // const SizedBox(height: 20),
                // Topics List (Bullet points style)
                //TopicsList(topics: _topics),

                // AI Neural Visualizer
                Expanded(
                  child: Center(
                    child: AINeuralVisualizer(
                      isListening: _conversationState == ConversationState.listening,
                      isProcessing: _conversationState == ConversationState.processing,
                      size: 300,
                      primaryColor: const Color(0xFF00D4FF),
                      secondaryColor: const Color(0xFF6C63FF),
                      accentColor: const Color(0xFF818CF8),
                    ),
                  ),
                ),

                // Two Liners Chat Text
                ChatDisplay(
                  messages: _chatMessages,
                  statusText: _statusText,
                ),

                const SizedBox(height: 40),

                // Mic Button
                MicButton(
                  state: _conversationState,
                  onTap: _conversationState != ConversationState.idle ? _stopChat : _startChat,
                ),

                const SizedBox(height: 60),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
