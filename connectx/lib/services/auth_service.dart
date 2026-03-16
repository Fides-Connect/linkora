import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'dart:io' show SocketException;
import 'package:flutter/foundation.dart'
    show debugPrint, kIsWeb, defaultTargetPlatform, TargetPlatform;

import 'dart:convert' show json;
import 'package:http/http.dart' as http;
import 'user_service.dart';
import 'webrtc_service.dart';

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;
  GoogleSignIn? _googleSignIn;

  final UserService _userService = UserService();
  WebRTCService? _webrtcService;

  User? get currentUser => _firebaseAuth.currentUser;
  Stream<User?> get onCurrentUserChanged => _firebaseAuth.authStateChanges();

  String? _photoUrl;

  /// Expose the photo URL from Firebase user.
  String? get photoUrl => _photoUrl ?? currentUser?.photoURL;

  // Simple init guard
  bool _initialized = false;

  /// Set WebRTC service to enable auto-connect after sign-in
  void setWebRTCService(WebRTCService webrtcService) {
    _webrtcService = webrtcService;
  }

  /// Initialize Firebase and Google Sign-In.
  Future<void> initialize() async {
    if (_initialized) return;

    // Initialize FCM in the background — do not block app startup on a network call.
    unawaited(_userService.initializeFCM());

    // Initialize GoogleSignIn with proper configuration
    final bool isAndroid =
        !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    final String? webClientId = dotenv.env['GOOGLE_OAUTH_CLIENT_ID'];

    if (isAndroid) {
      if (webClientId == null || webClientId.isEmpty) {
        throw Exception(
          'GOOGLE_OAUTH_CLIENT_ID must be set in .env for Android',
        );
      }
      _googleSignIn = GoogleSignIn.instance;
      await _googleSignIn!.initialize(serverClientId: webClientId);
    } else {
      _googleSignIn = GoogleSignIn.instance;
    }

    // Listen to auth state changes
    _firebaseAuth.authStateChanges().listen(_handleAuthStateChanged);

    _initialized = true;
  }

  Future<void> _handleAuthStateChanged(User? user) async {
    if (user != null) {
      _photoUrl = user.photoURL;
    } else {
      _photoUrl = null;
    }
  }

  /// Perform post-auth work: sync user record, connect WebRTC, validate with
  /// backend. Called by [UserProvider] after Firebase auth fires, awaited
  /// before navigating to the home screen so the home page never sees a 404
  /// on /me due to a sync race.
  Future<void> performSyncAndConnect(User user) async {
    // Sync user with backend (creates Firestore document if first sign-in)
    await _userService.syncUserWithBackend();

    // Auto-connect to WebRTC if service is available
    if (_webrtcService != null) {
      await _webrtcService!.connect();
    }

    // Validate with backend if configured — soft failure only, never sign out.
    final String? serverUrl = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (serverUrl != null && serverUrl.isNotEmpty) {
      // Mirror WebRTCService logic: skip backend validation for local endpoints.
      // Bare hosts (e.g. localhost:8080 and 10.0.2.2:8080 for the Android
      // emulator) and explicit http:// prefixes are all treated as local dev.
      final bool isLocalHttp =
          serverUrl.startsWith('http://localhost') ||
          serverUrl.startsWith('http://10.0.2.2') ||
          serverUrl.startsWith('localhost') ||
          serverUrl.startsWith('10.0.2.2');
      if (!isLocalHttp) {
        final idToken = await user.getIdToken();
        if (idToken != null) {
          final bool valid = await _signInBackend(idToken);
          if (!valid) {
            debugPrint(
              'Backend validation failed or backend unreachable — continuing as authenticated.',
            );
            // Do not sign out: a missing or unreachable backend must not
            // prevent the user from using the app.
          }
        }
      }
    }
  }

  Future<void> signOut() async {
    // Logout from backend first
    await _userService.logout();

    await _googleSignIn?.signOut();
    await _firebaseAuth.signOut();
    _photoUrl = null;
  }

  Future<UserCredential?> signInWithGoogle() async {
    if (_googleSignIn == null) {
      throw Exception('GoogleSignIn not initialized. Call initialize() first.');
    }

    try {
      // Trigger the Google Sign-In flow
      final GoogleSignInAccount googleUser = await _googleSignIn!.authenticate(
        scopeHint: ['openid', 'email', 'profile'],
      );

      // Obtain the auth details from the request
        final GoogleSignInAuthentication googleAuth =
          googleUser.authentication;

      // Create a new credential with just the idToken
      // Note: google_sign_in 7.2.0+ no longer provides accessToken separately
      final credential = GoogleAuthProvider.credential(
        idToken: googleAuth.idToken,
      );

      // Sign in to Firebase with the Google credential
      final userCredential = await _firebaseAuth.signInWithCredential(
        credential,
      );

      return userCredential;
    } catch (e) {
      debugPrint('Sign-in error: $e');
      rethrow;
    }
  }

  Future<bool> _signInBackend(String idToken) async {
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      return false;
    }
    final String baseUrl = rawServer.startsWith('http')
        ? rawServer
        : 'http://$rawServer';
    final String url = '$baseUrl/api/v1/auth/sign-in-google';

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
          'Backend validation failed: ${response.statusCode} - ${response.body}',
        );
        return false;
      }

      // Server should return a boolean 'is_valid' field
      try {
        final Map<String, dynamic> data =
            json.decode(response.body) as Map<String, dynamic>;
        return data['is_valid'] as bool? ?? true;
      } catch (e) {
        // Treat 200 as valid even if response format is unexpected
        return true;
      }
    } on TimeoutException catch (_) {
      debugPrint('Backend validation timeout (6s)');
      return false;
    } on SocketException catch (e) {
      debugPrint('Backend validation network error: ${e.message}');
      return false;
    } catch (e) {
      debugPrint('Backend validation error: $e');
      return false;
    }
  }
}
