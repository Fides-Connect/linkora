import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform, debugPrint;

import 'dart:convert' show json;
import 'package:http/http.dart' as http;

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  bool isAuthorized = false;
  GoogleSignInAccount? _currentUser;
  GoogleSignInAccount? get currentUser => _currentUser;
  final StreamController<GoogleSignInAccount?> _userController =
      StreamController.broadcast();
  Stream<GoogleSignInAccount?> get onCurrentUserChanged =>
      _userController.stream;

  String? _photoUrl;

  /// Expose the photo URL fetched from People API (may be null).
  String? get photoUrl => _photoUrl;

  final List<String> scopes = <String>['openid', 'email', 'profile'];

  // simple init guard
  bool _initialized = false;

  /// Initialize the underlying GoogleSignIn singleton with optional clientId.
  Future<void> initialize() async {
    if (_initialized) return;
    final bool isWeb = kIsWeb;
    final bool isAndroid =
        !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

    final webClientId = dotenv.env['GOOGLE_OAUTH_CLIENT_ID'];
    if (webClientId == null) {
      throw Exception(
        'GOOGLE_OAUTH_CLIENT_ID not set. Add GOOGLE_OAUTH_CLIENT_ID to .env',
      );
    }

    // Await the initialization and register listener
    await GoogleSignIn.instance.initialize(
      clientId: isWeb ? webClientId : null,
      serverClientId: isAndroid ? webClientId : null,
    );

    // Listen for authentication events (store/attach errors to service-level handler)
    GoogleSignIn.instance.authenticationEvents
        .listen(_handleAuthenticationEvent)
        .onError(_handleAuthenticationError);
    
    _initialized = true;
  }

  Future<void> _handleAuthenticationEvent(
    GoogleSignInAuthenticationEvent event,
  ) async {
    debugPrint('Auth event: $event');
    final GoogleSignInAccount? user;
    if (event is GoogleSignInAuthenticationEventSignIn) {
      user = event.user;
    } else if (event is GoogleSignInAuthenticationEventSignOut) {
      user = null;
    } else {
      user = null;
    }

    _userController.add(user);
    _currentUser = user;

    if (_currentUser != null) {
      _handleGetContact(_currentUser!);
    }
  }

  Future<void> _handleAuthenticationError(Object e) async {
    debugPrint('Auth error: $e');
    _userController.add(null);
    _currentUser = null;
  }

  // Calls the People API REST endpoint for the signed-in user to retrieve information.
  Future<void> _handleGetContact(GoogleSignInAccount user) async {
    final Map<String, String>? headers = await user.authorizationClient
        .authorizationHeaders(scopes);
    if (headers == null) {
      return;
    }

    // Request photos explicitly using personFields
    final http.Response response = await http.get(
      Uri.parse(
        'https://people.googleapis.com/v1/people/me?personFields=names,photos',
      ),
      headers: headers,
    );

    if (response.statusCode != 200) {
      return;
    }

    final Map<String, dynamic> profile = json.decode(response.body);
    // Extract photo url (if any)
    final List<dynamic>? photos = profile['photos'] as List<dynamic>?;
    String? photoUrl;
    if (photos != null && photos.isNotEmpty) {
      try {
        final Map<String, dynamic> first =
            photos.firstWhere(
                  (p) =>
                      (p as Map<String, dynamic>)['metadata']?['primary'] ==
                      true,
                  orElse: () => photos.first,
                )
                as Map<String, dynamic>;
        photoUrl = first['url'] as String?;
      } catch (e) {
        debugPrint('DEBUG: photo parsing error: $e');
        photoUrl = null;
      }
    } else {
      photoUrl = null;
    }
    debugPrint('DEBUG: resolved photoUrl -> $photoUrl');

    // store or expose photoUrl for UI usage
    // save and notify listeners so UI can update
    _photoUrl = photoUrl;
    _userController.add(_currentUser);
  }

  Future<void> signOut() async {
    // Disconnect instead of just signing out, to reset the example state as
    // much as possible.
    await GoogleSignIn.instance.disconnect();
  }

  Future<void> signIn() async {
    await GoogleSignIn.instance.authenticate(scopeHint: scopes);
  }

    void dispose() {
    try {
      _userController.close();
    } catch (_) {}
  }
}
