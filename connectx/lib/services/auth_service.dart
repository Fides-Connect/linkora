import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform, debugPrint;

/// Lightweight wrapper around the new google_sign_in v7 API.

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  late final GoogleSignIn _googleSignIn;
  bool _isInitialized = false;
  GoogleSignInAccount? _current;
  final StreamController<GoogleSignInAccount?> _userController =
      StreamController.broadcast();

  GoogleSignInAccount? get currentUser => _current;
  Stream<GoogleSignInAccount?> get onCurrentUserChanged =>
      _userController.stream;

  /// Initialize the underlying GoogleSignIn singleton with optional clientId.
  Future<void> initialize() async {
    if (_isInitialized) {
      debugPrint('AuthService: already initialized, skipping');
      return;
    }
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
    await GoogleSignIn.instance.initialize(
      clientId: isWeb ? webClientId : null,
      serverClientId: isAndroid ? webClientId : null,
    );
    _googleSignIn = GoogleSignIn.instance;

    // Listen to authentication events to keep cached current user up-to-date
    _googleSignIn.authenticationEvents.listen((event) {
      if (event is GoogleSignInAuthenticationEventSignIn) {
        _current = event.user;
        _userController.add(_current);
      } else if (event is GoogleSignInAuthenticationEventSignOut) {
        _current = null;
        _userController.add(null);
      }
    });

    // Mark as initialized
    _isInitialized = true;
  }

  /// Interactive sign in. Returns the authenticated account or throws on error.
  Future<GoogleSignInAccount> signIn() async {
    // authenticate() throws on error and returns an account on success
    final account = await _googleSignIn.authenticate();
    _current = account;
    _userController.add(_current);
    return account;
  }

  /// Try a lightweight / silent sign-in. May return null if no sign-in restored.
  Future<GoogleSignInAccount?> signInSilently() async {
    final Future<GoogleSignInAccount?>? result = _googleSignIn
        .attemptLightweightAuthentication();
    if (result == null) return null;
    return await result;
  }

  /// Sign out the current user.
  Future<void> signOut() async {
    await _googleSignIn.signOut();
    _current = null;
    _userController.add(null);
  }
}
