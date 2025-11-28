import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter/foundation.dart' show debugPrint;
import 'dart:convert' show json;
import 'package:http/http.dart' as http;
import 'dart:async';
import 'dart:io' show SocketException;


class UserService {
  // Singleton factory
  static final UserService _instance = UserService._internal();
  factory UserService() => _instance;
  UserService._internal();

  final FirebaseMessaging _firebaseMessaging = FirebaseMessaging.instance;
  
  String? _fcmToken;
  Map<String, dynamic>? _userProfile;
  
  /// Get the current FCM token
  String? get fcmToken => _fcmToken;
  
  /// Get the current user profile
  Map<String, dynamic>? get userProfile => _userProfile;



  /// Initialize Firebase Cloud Messaging
  Future<void> initializeFCM() async {
    try {
      // Request notification permissions
      NotificationSettings settings = await _firebaseMessaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
        sound: true,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        debugPrint('User granted notification permission');
      } else if (settings.authorizationStatus == AuthorizationStatus.provisional) {
        debugPrint('User granted provisional notification permission');
      } else {
        debugPrint('User declined or has not accepted notification permission');
      }

      // Get the FCM token
      _fcmToken = await _firebaseMessaging.getToken();
      debugPrint('FCM Token: $_fcmToken');

      // Listen for token refresh
      _firebaseMessaging.onTokenRefresh.listen((newToken) {
        _fcmToken = newToken;
        debugPrint('FCM Token refreshed: $newToken');
        // TODO: Update token on backend when it refreshes
      });

    } catch (e) {
      debugPrint('Error initializing FCM: $e');
    }
  }



  /// Sync user data with the backend server
  /// Creates a new user or loads existing user profile and history
  Future<bool> syncUserWithBackend(User firebaseUser) async {
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      debugPrint('AI_ASSISTANT_SERVER_URL not configured');
      return false;
    }

    final String url = 'http://$rawServer/user/sync';
    
    try {
      // Get the ID token
      final String? idToken = await firebaseUser.getIdToken();
      if (idToken == null) {
        debugPrint('Failed to get ID token');
        return false;
      }

      // Prepare user data
      final Map<String, dynamic> userData = {
        'id_token': idToken,
        'user_id': firebaseUser.uid,
        'email': firebaseUser.email,
        'name': firebaseUser.displayName,
        'photo_url': firebaseUser.photoURL,
        'fcm_token': _fcmToken,
        'created_at': firebaseUser.metadata.creationTime?.toIso8601String(),
        'last_sign_in': firebaseUser.metadata.lastSignInTime?.toIso8601String(),
      };

      debugPrint('Syncing user data with backend: ${userData['email']}');

      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: json.encode(userData),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final Map<String, dynamic> data =
            json.decode(response.body) as Map<String, dynamic>;
        
        _userProfile = data['user_profile'];
        final bool isNewUser = data['is_new_user'] as bool? ?? false;
        final String userId = data['user_id'] as String;
        
        if (isNewUser) {
          debugPrint('New user created in database: $userId');
        } else {
          debugPrint('Existing user profile loaded from database: $userId');
        }
        
        return true;
      } else {
        debugPrint('User sync failed: ${response.statusCode} - ${response.body}');
        return false;
      }

    } on TimeoutException catch (_) {
      debugPrint('User sync timeout (10s)');
      return false;
    } on SocketException catch (e) {
      debugPrint('User sync network error: ${e.message}');
      return false;
    } catch (e) {
      debugPrint('User sync error: $e');
      return false;
    }
  }


  /// Clear user data on sign out
  void clearUserData() {
    _userProfile = null;
    _fcmToken = null;
  }

  
  /// Notify backend of user logout
  Future<void> notifyLogout(User firebaseUser) async {
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      debugPrint('AI_ASSISTANT_SERVER_URL not configured');
      return;
    }

    final String url = 'http://$rawServer/user/logout';
    
    try {
      // Get the ID token
      final String? idToken = await firebaseUser.getIdToken();
      if (idToken == null) {
        debugPrint('Failed to get ID token for logout');
        return;
      }

      final Map<String, dynamic> logoutData = {
        'id_token': idToken,
        'user_id': firebaseUser.uid,
      };

      debugPrint('Notifying backend of logout: ${firebaseUser.email}');

      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: json.encode(logoutData),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        debugPrint('Backend logout successful');
      } else {
        debugPrint('Backend logout failed: ${response.statusCode}');
      }

    } on TimeoutException catch (_) {
      debugPrint('Backend logout timeout');
    } on SocketException catch (e) {
      debugPrint('Backend logout network error: ${e.message}');
    } catch (e) {
      debugPrint('Backend logout error: $e');
    }
  }
}
