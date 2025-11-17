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

  // late final GoogleSignIn _googleSignIn;
  final StreamController<GoogleSignInAccount?> _userController =
      StreamController.broadcast();

  GoogleSignInAccount? get currentUser => _currentUser;
  Stream<GoogleSignInAccount?> get onCurrentUserChanged =>
      _userController.stream;

  GoogleSignInAccount? _currentUser;
  bool isAuthorized = false; // has granted permissions?
  String _contactText = '';
  String _errorMessage = '';
  String _serverAuthCode = '';
  String? _photoUrl;

  /// Expose the photo URL fetched from People API (may be null).
  String? get photoUrl => _photoUrl;

  final List<String> scopes = <String>[
    'openid',
    'email',
    'profile',
  ];

  /// Initialize the underlying GoogleSignIn singleton with optional clientId.
  Future<void> initialize() async {
    final bool isWeb = kIsWeb;
    final bool isAndroid =
        !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

    final webClientId = dotenv.env['GOOGLE_OAUTH_CLIENT_ID_WEB'];
    if (webClientId == null) {
      throw Exception(
        'GOOGLE_OAUTH_CLIENT_ID not set. Add GOOGLE_OAUTH_CLIENT_ID_WEB to .env',
      );
    }
    // Configure the package singleton with the right IDs, then use the singleton.
    unawaited(
      GoogleSignIn.instance
          .initialize(
            clientId: isWeb ? webClientId : null,
            serverClientId: isAndroid ? webClientId : null,
          )
          .then((_) {
            GoogleSignIn.instance.authenticationEvents
                .listen(_handleAuthenticationEvent)
                .onError(_handleAuthenticationError);

            /// This example always uses the stream-based approach to determining
            /// which UI state to show, rather than using the future returned here,
            /// if any, to conditionally skip directly to the signed-in state.
            //signIn.attemptLightweightAuthentication();
          }),
    );
  }

  Future<void> _handleAuthenticationEvent(
    GoogleSignInAuthenticationEvent event,
  ) async {
    debugPrint('Auth event: $event');
    final GoogleSignInAccount? user = // ...
        switch (event) {
          GoogleSignInAuthenticationEventSignIn() => event.user,
          GoogleSignInAuthenticationEventSignOut() => null,
        };

    // Check for existing authorization.
    final GoogleSignInClientAuthorization? authorization = await user
        ?.authorizationClient
        .authorizeScopes(scopes);

    debugPrint('User: $user, Authorization: $authorization');
    debugPrint('Photo URL: ${user?.photoUrl}');
    _userController.add(user);
    _currentUser = user;
    isAuthorized = authorization != null;
    _errorMessage = '';

    // If the user has already granted access to the required scopes, call the
    // REST API.
    if (user != null && authorization != null) {
      unawaited(_handleGetContact(user));
    }
  }

  Future<void> _handleAuthenticationError(Object e) async {
    debugPrint('Auth error: $e');
    _userController.add(null);
    _currentUser = null;
    isAuthorized = false;
    _errorMessage = e is GoogleSignInException
        ? _errorMessageFromSignInException(e)
        : 'Unknown error: $e';
  }

  // Calls the People API REST endpoint for the signed-in user to retrieve information.
  Future<void> _handleGetContact(GoogleSignInAccount user) async {
    _contactText = 'Loading contact info...';

    final Map<String, String>? headers = await user.authorizationClient
        .authorizationHeaders(scopes);
    debugPrint('DEBUG: authorization headers -> $headers');
    if (headers == null) {
      _contactText = '';
      _errorMessage = 'Failed to construct authorization headers.';
      return;
    }

    // Request photos explicitly using personFields
    final http.Response response = await http.get(
      Uri.parse(
        'https://people.googleapis.com/v1/people/me?personFields=names,photos',
      ),
      headers: headers,
    );
    debugPrint('DEBUG: People API response code=${response.statusCode}');
    debugPrint('DEBUG: People API response body=${response.body}');

    if (response.statusCode != 200) {
      _contactText = '';
      _errorMessage = 'People API returned ${response.statusCode}';
      return;
    }

    final Map<String, dynamic> profile = json.decode(response.body);
    debugPrint('DEBUG: People API parsed profile keys=${profile.keys}');
    // Extract display name and photo url (if any)
    final String? displayName = (profile['names'] as List<dynamic>?)
        ?.cast<Map<String, dynamic>>()
        .firstWhere(
          (n) => n['metadata']?['primary'] == true,
          orElse: () =>
              (profile['names'] as List<dynamic>).first as Map<String, dynamic>,
        )['displayName'] as String?;
    final List<dynamic>? photos = profile['photos'] as List<dynamic>?;
    debugPrint('DEBUG: photos raw -> $photos');
    String? photoUrl;
    if (photos != null && photos.isNotEmpty) {
      try {
        final Map<String, dynamic> first = photos.firstWhere(
          (p) => (p as Map<String, dynamic>)['metadata']?['primary'] == true,
          orElse: () => photos.first,
        ) as Map<String, dynamic>;
        photoUrl = first['url'] as String?;
      } catch (e) {
        debugPrint('DEBUG: photo parsing error: $e');
        photoUrl = null;
      }
    } else {
      photoUrl = null;
    }
    debugPrint('DEBUG: resolved photoUrl -> $photoUrl');

    _contactText = displayName ?? user.displayName ?? '';
    // Extract the access token from authorization headers returned earlier.
    // The headers map should contain an Authorization: Bearer <token> entry.
    final String? authHeader = headers['Authorization'] ?? headers['authorization'];
    if (authHeader != null && authHeader.startsWith('Bearer ')) {
      _serverAuthCode = authHeader.substring(7);
    } else {
      _serverAuthCode = authHeader ?? '';
    }
    // store or expose photoUrl for UI usage
    debugPrint('Fetched photoUrl from People API: $photoUrl');
    // save and notify listeners so UI can update
    _photoUrl = photoUrl;
    _userController.add(_currentUser);
    // ...update state / controllers as needed...
  }

  String? _pickFirstNamedContact(Map<String, dynamic> data) {
    final List<dynamic>? connections = data['connections'] as List<dynamic>?;
    final Map<String, dynamic>? contact =
        connections?.firstWhere(
              (dynamic contact) =>
                  (contact as Map<Object?, dynamic>)['names'] != null,
              orElse: () => null,
            )
            as Map<String, dynamic>?;
    if (contact != null) {
      final List<dynamic> names = contact['names'] as List<dynamic>;
      final Map<String, dynamic>? name =
          names.firstWhere(
                (dynamic name) =>
                    (name as Map<Object?, dynamic>)['displayName'] != null,
                orElse: () => null,
              )
              as Map<String, dynamic>?;
      if (name != null) {
        return name['displayName'] as String?;
      }
    }
    return null;
  }

  String _errorMessageFromSignInException(GoogleSignInException e) {
    // In practice, an application should likely have specific handling for most
    // or all of the, but for simplicity this just handles cancel, and reports
    // the rest as generic errors.
    return switch (e.code) {
      GoogleSignInExceptionCode.canceled => 'Sign in canceled',
      _ => 'GoogleSignInException ${e.code}: ${e.description}',
    };
  }

  Future<void> signOut() async {
    // Disconnect instead of just signing out, to reset the example state as
    // much as possible.
    await GoogleSignIn.instance.disconnect();
  }

  Future<void> signIn() async {
    try {
      await GoogleSignIn.instance.authenticate(scopeHint: scopes);
    } catch (e) {
      _errorMessage = e.toString();
    }
  }
}
