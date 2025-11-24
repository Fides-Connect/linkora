import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'dart:io' show SocketException;
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb, defaultTargetPlatform, TargetPlatform;

import 'dart:convert' show json;
import 'package:http/http.dart' as http;

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;
  GoogleSignIn? _googleSignIn;

  User? get currentUser => _firebaseAuth.currentUser;
  Stream<User?> get onCurrentUserChanged => _firebaseAuth.authStateChanges();

  String? _photoUrl;

  /// Expose the photo URL from Firebase user profile.
  String? get photoUrl => _photoUrl ?? currentUser?.photoURL;

  // Simple init guard
  bool _initialized = false;

  /// Initialize Firebase and Google Sign-In.
  Future<void> initialize() async {
    if (_initialized) return;
    
    // Initialize GoogleSignIn with proper configuration
    final bool isAndroid = !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    final String? webClientId = dotenv.env['GOOGLE_OAUTH_CLIENT_ID'];
    
    if (isAndroid) {
      if (webClientId == null || webClientId.isEmpty) {
        throw Exception('GOOGLE_OAUTH_CLIENT_ID must be set in .env for Android');
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
      
      // Validate with backend if configured
      final String? serverUrl = dotenv.env['AI_ASSISTANT_SERVER_URL'];
      if (serverUrl != null && serverUrl.isNotEmpty && serverUrl != 'localhost:8080') {
        final idToken = await user.getIdToken();
        if (idToken != null) {
          final bool valid = await _signInBackend(idToken);
          if (!valid) {
            debugPrint('Backend validation failed - signing out');
            await signOut();
            return;
          }
        }
      }
    } else {
      _photoUrl = null;
    }
  }

  Future<void> signOut() async {
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
      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;

      // Create a new credential with just the idToken
      // Note: google_sign_in 7.2.0+ no longer provides accessToken separately
      final credential = GoogleAuthProvider.credential(
        idToken: googleAuth.idToken,
      );

      // Sign in to Firebase with the Google credential
      final userCredential = await _firebaseAuth.signInWithCredential(credential);
      
      return userCredential;
    } catch (e) {
      debugPrint('Sign-in error: $e');
      rethrow;
    }
  }

  // Legacy method name for backwards compatibility
  Future<UserCredential?> signIn() => signInWithGoogle();

  Future<UserCredential> signInWithEmail(String email, String password) async {
    try {
      final userCredential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      return userCredential;
    } catch (e) {
      debugPrint('Email sign-in error: $e');
      rethrow;
    }
  }

  Future<UserCredential> createUserWithEmail(String email, String password) async {
    try {
      final userCredential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      return userCredential;
    } catch (e) {
      debugPrint('Email registration error: $e');
      rethrow;
    }
  }

  Future<void> signInWithPhone(
    String phoneNumber, {
    required void Function(String verificationId, int? resendToken) codeSent,
    required void Function(FirebaseAuthException error) verificationFailed,
    required void Function(PhoneAuthCredential credential) verificationCompleted,
    required void Function(String verificationId) codeAutoRetrievalTimeout,
  }) async {
    try {
      await _firebaseAuth.verifyPhoneNumber(
        phoneNumber: phoneNumber,
        verificationCompleted: verificationCompleted,
        verificationFailed: verificationFailed,
        codeSent: codeSent,
        codeAutoRetrievalTimeout: codeAutoRetrievalTimeout,
      );
    } catch (e) {
      debugPrint('Phone sign-in error: $e');
      rethrow;
    }
  }

  Future<UserCredential> verifyPhoneCode(String verificationId, String smsCode) async {
    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: verificationId,
        smsCode: smsCode,
      );
      final userCredential = await _firebaseAuth.signInWithCredential(credential);
      return userCredential;
    } catch (e) {
      debugPrint('Phone verification error: $e');
      rethrow;
    }
  }

  Future<bool> _signInBackend(String idToken) async {
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      return false;
    }
    final String url = 'http://$rawServer/sign_in_google';

    try {
      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'id_token': idToken}),
          )
          .timeout(const Duration(seconds: 6));

      if (response.statusCode != 200) {
        debugPrint('Backend validation failed: ${response.statusCode} - ${response.body}');
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
