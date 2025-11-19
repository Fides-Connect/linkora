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

  // Simple init guard
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
    // Extract user from event
    final GoogleSignInAccount? user =
        event is GoogleSignInAuthenticationEventSignIn ? event.user : null;

    // Validate token with AI-Assistant server before accepting it locally
    final String? idToken = user?.authentication.idToken;
    if (idToken != null) {
      final bool valid = await _validateGoogleSignIn(idToken);
      if (!valid) {
        debugPrint('ID token validation failed - signing out locally');
        signOut();
        return;
      } else {
        // fetch profile photo, update current user and notify listeners
        _getProfilePhoto(user!);
        _currentUser = user;
        _userController.add(user);
      }
    }
  }

  Future<void> _handleAuthenticationError(Object e) async {
    debugPrint('Auth error: $e');
    _userController.add(null);
    _currentUser = null;
  }

  // Calls the People API REST endpoint for the signed-in user to retrieve information.
  Future<void> _getProfilePhoto(GoogleSignInAccount user) async {
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
      debugPrint('Failed to fetch user profile: ${response.body}');
      return;
    }

    final Map<String, dynamic> profile = json.decode(response.body);
    // Extract photo url (if any)
    final List<dynamic>? photos = profile['photos'] as List<dynamic>?;
    final photoUrl = photos?.isNotEmpty == true
        ? photos?.first['url'] as String?
        : null;

    // store photoUrl for UI usage
    _photoUrl = photoUrl;

    // Update current user and notify listeners
    _currentUser = user;
    _userController.add(user);
  }

  Future<void> signOut() async {
    // Disconnect instead of just signing out, to reset the example state as
    // much as possible.
    debugPrint('Signing out user ${_currentUser?.email}');
    await GoogleSignIn.instance.disconnect();
    _userController.add(null);
    _currentUser = null;
    _photoUrl = null;
  }

  Future<void> signIn() async {
    await GoogleSignIn.instance.authenticate(scopeHint: scopes);
  }

  /// Validate Google ID token with the AI-Assistant server endpoint.
  /// Returns true if the server accepts the token.
  Future<bool> _validateGoogleSignIn(String idToken) async {
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      debugPrint(
        'AI_ASSISTANT_SERVER_URL not set in .env. Cannot validate ID token.',
      );
      return false;
    }
    final String url = 'http://$rawServer/validate-google-signin';

    try {
      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'id_token': idToken}),
          )
          .timeout(const Duration(seconds: 6));

      if (response.statusCode != 200) {
        debugPrint(
          'Validation request failed: ${response.statusCode} ${response.body}',
        );
        return false;
      }

      // Server should return a boolean 'valid' field; if absent, treat 200 as valid.
      final Map<String, dynamic> data =
          json.decode(response.body) as Map<String, dynamic>;
      return (data['valid'] is bool) ? data['valid'] as bool : true;
    } catch (e) {
      debugPrint('Validation error: $e');
      return false;
    }
  }
}
