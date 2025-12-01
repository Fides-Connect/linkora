import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb, defaultTargetPlatform, TargetPlatform;

import 'user_service.dart';
import 'webrtc_service.dart';

class AuthService {
  // Singleton factory
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  // Lazy initialization to support testing
  FirebaseAuth? _firebaseAuthInstance;
  FirebaseAuth get _firebaseAuth {
    _firebaseAuthInstance ??= FirebaseAuth.instance;
    return _firebaseAuthInstance!;
  }
  
  GoogleSignIn? _googleSignIn;
  final UserService _userService = UserService();
  WebRTCService? _webrtcService;

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
    
    // Initialize FCM
    await _userService.initializeFCM();
    
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

  /// Set the WebRTC service to enable automatic connection on sign-in
  void setWebRTCService(WebRTCService service) {
    _webrtcService = service;
  }

  Future<void> _handleAuthStateChanged(User? user) async {
    if (user != null) {
      _photoUrl = user.photoURL;
      
      // Sync user data with backend
      final String? serverUrl = dotenv.env['AI_ASSISTANT_SERVER_URL'];
      if (serverUrl != null && serverUrl.isNotEmpty && serverUrl != 'localhost:8080') {
        final bool synced = await _userService.syncUserWithBackend(user);
        if (!synced) {
          debugPrint('User sync failed - but continuing with local auth');
        } else {
          // User synced successfully, now automatically connect to WebRTC
          await _connectToServer();
        }
      }
    } else {
      _photoUrl = null;
      _userService.clearUserData();
      
      // Disconnect from server on sign out
      _webrtcService?.disconnect();
    }
  }

  /// Automatically connect to AI assistant server after successful authentication
  Future<void> _connectToServer() async {
    if (_webrtcService == null) {
      debugPrint('AuthService: WebRTC service not set, skipping automatic connection');
      return;
    }

    try {
      debugPrint('AuthService: Automatically connecting to AI assistant server...');
      await _webrtcService!.connect();
      debugPrint('AuthService: Successfully connected to AI assistant server');
    } catch (e) {
      debugPrint('AuthService: Failed to auto-connect to server: $e');
      // Don't block authentication if connection fails
    }
  }

  Future<void> signOut() async {
    // Disconnect from server first and disable reconnection
    _webrtcService?.disableReconnection();
    _webrtcService?.disconnect();
    
    // Notify backend of logout before signing out
    final user = currentUser;
    if (user != null) {
      await _userService.notifyLogout(user);
    }
    
    await _googleSignIn?.signOut();
    await _firebaseAuth.signOut();
    _photoUrl = null;
    _userService.clearUserData();
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
}
