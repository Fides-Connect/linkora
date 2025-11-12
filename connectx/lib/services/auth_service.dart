import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';

/// Lightweight wrapper around the new google_sign_in v7 API.

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  GoogleSignInAccount? _current;
  final StreamController<GoogleSignInAccount?> _userController = StreamController.broadcast();

  GoogleSignInAccount? get currentUser => _current;
  Stream<GoogleSignInAccount?> get onCurrentUserChanged => _userController.stream;

  /// Initialize the underlying GoogleSignIn singleton with optional clientId.
  Future<void> initialize({String? clientId}) async {
    final effectiveClientId = clientId ?? dotenv.env['GOOGLE_CLIENT_ID'];
    await GoogleSignIn.instance.initialize(
      clientId: effectiveClientId,
    );
    // Listen to authentication events to keep cached current user up-to-date
    GoogleSignIn.instance.authenticationEvents.listen((event) {
      if (event is GoogleSignInAuthenticationEventSignIn) {
        _current = event.user;
        _userController.add(_current);
      } else if (event is GoogleSignInAuthenticationEventSignOut) {
        _current = null;
        _userController.add(null);
      }
    });
  }

  /// Interactive sign in. Returns the authenticated account or throws on error.
  Future<GoogleSignInAccount> signIn() async {
    // authenticate() throws on error and returns an account on success
    final account = await GoogleSignIn.instance.authenticate();
    _current = account;
    _userController.add(_current);
    return account;
  }

  /// Try a lightweight / silent sign-in. May return null if no sign-in restored.
  Future<GoogleSignInAccount?> signInSilently() async {
    final Future<GoogleSignInAccount?>? result =
        GoogleSignIn.instance.attemptLightweightAuthentication();
    if (result == null) return null;
    return await result;
  }

  /// Sign out the current user.
  Future<void> signOut() async {
    await GoogleSignIn.instance.signOut();
    _current = null;
    _userController.add(null);
  }
}
