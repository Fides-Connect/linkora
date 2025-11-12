import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Lightweight wrapper around the new google_sign_in v7 API.
class AuthService {
  AuthService();

  /// Initialize the underlying GoogleSignIn singleton with optional clientId.
  Future<void> initialize({String? clientId}) async {
    final effectiveClientId = clientId ?? dotenv.env['GOOGLE_CLIENT_ID'];
    await GoogleSignIn.instance.initialize(
      clientId: effectiveClientId,
    );
  }

  /// Interactive sign in. Returns the authenticated account or throws on error.
  Future<GoogleSignInAccount> signIn() async {
    // authenticate() throws on error and returns an account on success
    return await GoogleSignIn.instance.authenticate();
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
  }
}
