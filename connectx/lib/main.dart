import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/providers/user_provider.dart';
import 'features/auth/presentation/pages/start_page.dart';
import 'features/auth/presentation/widgets/auth_guard.dart';
import 'features/home/presentation/pages/home_page.dart';
import 'firebase_options.dart';
import 'localization/app_localizations.dart';
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

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => UserProvider()),
      ],
      child: const ConnectXApp(),
    ),
  );
}

class ConnectXApp extends StatefulWidget {
  const ConnectXApp({super.key});

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
      home: Consumer<UserProvider>(
        builder: (context, userProvider, child) {
          if (userProvider.isLoading && userProvider.user == null) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          
          if (userProvider.isAuthenticated) {
            return const ConnectXHomePage();
          } else {
            return const StartPage();
          }
        },
      ),
      routes: {
        '/start': (context) => const StartPage(),
        '/home': (context) => const AuthGuard(
              child: ConnectXHomePage(),
            ),
      },
      debugShowCheckedModeBanner: false,
    );
  }
}
