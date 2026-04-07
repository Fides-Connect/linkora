import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/providers/user_provider.dart';
import 'features/auth/presentation/pages/start_page.dart';
import 'features/auth/presentation/widgets/auth_guard.dart';
import 'features/home/data/repositories/home_repository.dart';
import 'features/home/presentation/pages/home_page.dart';
import 'features/home/presentation/pages/request_detail_page.dart';
import 'features/home/presentation/viewmodels/home_tab_view_model.dart';
import 'firebase_options.dart';
import 'localization/app_localizations.dart';
import 'services/notification_service.dart';
import 'services/user_service.dart';
import 'theme.dart';

/// Global navigator key — used to push routes from outside the widget tree
/// (e.g. when a push notification is tapped).
final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

/// Fetches the service request with [requestId] from the backend and pushes
/// [RequestDetailPage] onto the navigator stack. Silently ignored if the
/// request cannot be fetched or the navigator is not yet ready.
Future<void> _openServiceRequestDetail(String requestId) async {
  if (requestId.isEmpty) return;
  final context = _navigatorKey.currentContext;
  if (context == null) return;
  final repo = HomeRepository();
  final request = await repo.getRequest(requestId);
  if (request == null) return;
  if (!context.mounted) return;
  final viewModel = HomeTabViewModel();
  // Load user data so getType/getAmount/action buttons work correctly.
  await viewModel.loadData();
  if (!context.mounted) return;
  Navigator.of(context)
      .push(
        MaterialPageRoute(
          builder: (_) => ChangeNotifierProvider.value(
            value: viewModel,
            child: RequestDetailPage(request: request),
          ),
        ),
      )
      .then((_) => viewModel.dispose());
}

/// Handles an FCM [RemoteMessage] that opens the app (background / terminated).
void _handleNotificationOpen(RemoteMessage? message) {
  if (message == null) return;
  final type = message.data['type'];
  if (type == 'service_request_status_change' ||
      type == 'new_service_request') {
    final id = message.data['service_request_id'] ?? '';
    _openServiceRequestDetail(id);
  }
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

  final isLiteMode = dotenv.env['APP_MODE']?.toLowerCase() == 'lite';

  if (!isLiteMode) {
    // Set up background message handler
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // Show a local notification when the app is in the foreground and a
    // service-request status-change push arrives (FCM does not auto-display
    // notification-payload messages while the app is active).
    // Tapping the local notification calls _openServiceRequestDetail.
    final notificationService = NotificationService();
    await notificationService.initialize(
      onNotificationTap: (payload) {
        // payload format: "<type>:<service_request_id>"
        final colonIndex = payload.indexOf(':');
        if (colonIndex != -1) {
          final id = payload.substring(colonIndex + 1);
          _openServiceRequestDetail(id);
        }
      },
    );
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      final type = message.data['type'];
      if (type == 'service_request_status_change' ||
          type == 'new_service_request') {
        final title = message.notification?.title ?? 'Service Request Update';
        final body = message.notification?.body ?? 'You have a new service request update.';
        notificationService.showNotification(
          id: DateTime.now().millisecondsSinceEpoch,
          title: title,
          body: body,
          payload: '$type:${message.data['service_request_id'] ?? ''}',
        );
      }
    });

    // Navigate to detail page when the app is opened via a notification tap
    // while the app was in the background.
    FirebaseMessaging.onMessageOpenedApp.listen(_handleNotificationOpen);

    // Navigate when the app was fully terminated and launched via notification.
    _handleNotificationOpen(
      await FirebaseMessaging.instance.getInitialMessage(),
    );
  }

  final userProvider = UserProvider();
  await userProvider.init();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: userProvider),
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

  UserProvider? _userProvider;
  bool? _prevAuthenticated;

  static const _kLanguageKey = 'lite_language';
  static final bool _isLiteMode =
      dotenv.env['APP_MODE']?.toLowerCase() == 'lite';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _userProvider = context.read<UserProvider>();
      _userProvider!.addListener(_onAuthChanged);
      if (_isLiteMode) {
        _restoreLocalLanguage();
      } else if (_userProvider!.isAuthenticated) {
        _applyBackendSettings();
      }
    });
  }

  @override
  void dispose() {
    _userProvider?.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    final isAuth = _userProvider?.isAuthenticated ?? false;
    if (isAuth && _prevAuthenticated != true && !_isLiteMode) _applyBackendSettings();
    _prevAuthenticated = isAuth;
  }

  /// Fetches language + notifications_enabled from the backend and applies
  /// them locally. Runs once after login and on each fresh authentication.
  ///
  /// Only used in full mode. In lite mode, [_restoreLocalLanguage] is used
  /// instead because the server has no persistent settings state.
  Future<void> _applyBackendSettings() async {
    final settings = await UserService().getSettings();
    if (settings == null || !mounted) return;
    final languageRaw = settings['language'];
    if (languageRaw is String) {
      final normalized = languageRaw.toLowerCase();
      if (normalized == 'en' || normalized == 'de') {
        setState(() => _locale = Locale(normalized, ''));
      }
    }
    final notificationsEnabledRaw = settings['notifications_enabled'];
    if (notificationsEnabledRaw is bool) {
      await NotificationService().setNotificationsEnabled(notificationsEnabledRaw);
    }
  }

  /// Restores the user's last-chosen language from local storage in lite mode.
  /// Falls back to the system locale (i.e. [_locale] stays null) if no
  /// preference has been saved yet.
  Future<void> _restoreLocalLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_kLanguageKey);
    if (saved != null && (saved == 'en' || saved == 'de') && mounted) {
      setState(() => _locale = Locale(saved, ''));
    }
  }

  void setLocale(Locale locale) {
    setState(() {
      _locale = locale;
    });
    if (_isLiteMode) {
      // Persist the choice locally — in lite mode there is no Firestore to
      // back this up, so shared_preferences is the source of truth.
      SharedPreferences.getInstance().then(
        (prefs) => prefs.setString(_kLanguageKey, locale.languageCode),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ConnectX',
      navigatorKey: _navigatorKey,
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
