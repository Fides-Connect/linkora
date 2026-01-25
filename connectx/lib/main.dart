import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'features/auth/presentation/pages/start_page.dart';
import 'features/auth/presentation/widgets/auth_guard.dart';
import 'features/home/presentation/pages/home_page.dart';
import 'firebase_options.dart';
import 'localization/app_localizations.dart';
import 'services/auth_service.dart';
import 'theme.dart';

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
      home: StreamBuilder(
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
