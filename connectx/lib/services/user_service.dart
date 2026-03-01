import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter/foundation.dart';
import 'api_service.dart';

/// Service for managing user sync, FCM token registration, and backend settings.
class UserService {
  // Singleton so the same instance is shared across the app.
  static final UserService _instance = UserService._internal();
  factory UserService() => _instance;
  UserService._internal();

  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  final ApiService _apiService = ApiService();

  String? _fcmToken;

  String? get fcmToken => _fcmToken;

  /// Initialize Firebase Cloud Messaging
  /// Requests notification permissions and gets FCM token
  Future<void> initializeFCM() async {
    try {
      // Request permission for notifications
      NotificationSettings settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        debugPrint('User granted notification permission');

        // Get FCM token
        _fcmToken = await _messaging.getToken();
        debugPrint('FCM Token: $_fcmToken');

        // Listen for token refresh
        _messaging.onTokenRefresh.listen((newToken) {
          _fcmToken = newToken;
          debugPrint('FCM Token refreshed: $newToken');
          // Sync new token with backend
          syncUserWithBackend();
        });
      } else {
        debugPrint('User declined notification permission');
      }
    } catch (e) {
      debugPrint('Error initializing FCM: $e');
    }
  }

  /// Sync user with backend
  /// Creates or updates user record with FCM token
  Future<Map<String, dynamic>?> syncUserWithBackend() async {
    try {
      User? user = _auth.currentUser;

      if (user == null) {
        debugPrint('No user signed in, cannot sync');
        return null;
      }

      // Always fetch the current token at sync time so we never send a stale
      // or null token due to a race with initializeFCM().
      final currentToken = _fcmToken ?? await _messaging.getToken();
      _fcmToken = currentToken; // keep cache in sync

      // Prepare user data
      final userData = {
        'user_id': user.uid,
        'name': user.displayName ?? '',
        'email': user.email ?? '',
        'photo_url': user.photoURL ?? '',
        'fcm_token': currentToken ?? '',
      };

      // Get backend URL from environment
      final serverUrl =
          dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? 'localhost:8080';
      final backendUrl = serverUrl.startsWith('http')
          ? serverUrl
          : 'http://$serverUrl';
      final url = Uri.parse('$backendUrl/api/v1/auth/sync');

      debugPrint('Syncing user with backend: ${user.uid}');

      // Make HTTP request
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(userData),
      );

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        debugPrint('User sync successful: ${responseData['status']}');
        return responseData;
      } else {
        debugPrint(
          'User sync failed: ${response.statusCode} - ${response.body}',
        );
        return null;
      }
    } catch (e) {
      debugPrint('Error syncing user with backend: $e');
      return null;
    }
  }

  /// Logout user from backend
  /// Optionally clears conversation history
  Future<bool> logout({bool clearHistory = false}) async {
    try {
      User? user = _auth.currentUser;

      if (user == null) {
        debugPrint('No user signed in');
        return false;
      }

      // Get backend URL from environment
      final serverUrl =
          dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? 'localhost:8080';
      final backendUrl = serverUrl.startsWith('http')
          ? serverUrl
          : 'http://$serverUrl';
      final url = Uri.parse('$backendUrl/api/v1/auth/logout');

      debugPrint('Logging out user: ${user.uid}');

      // Make HTTP request
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'user_id': user.uid}),
      );

      if (response.statusCode == 200) {
        debugPrint('User logout successful');
        return true;
      } else {
        debugPrint(
          'User logout failed: ${response.statusCode} - ${response.body}',
        );
        return false;
      }
    } catch (e) {
      debugPrint('Error logging out user: $e');
      return false;
    }
  }

  /// Fetch the current user's app settings from the backend.
  /// Returns `{'language': 'en', 'notifications_enabled': true}` or null on failure.
  Future<Map<String, dynamic>?> getSettings() async {
    try {
      final data = await _apiService.get('/api/v1/me/settings');
      return (data as Map<String, dynamic>?);
    } catch (e) {
      debugPrint('Error fetching settings: $e');
      return null;
    }
  }

  /// Persist app settings to the backend.
  /// Only the provided (non-null) fields are sent.
  Future<bool> updateSettings({
    String? language,
    bool? notificationsEnabled,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (language != null) body['language'] = language;
      if (notificationsEnabled != null) body['notifications_enabled'] = notificationsEnabled;
      if (body.isEmpty) return true;
      await _apiService.patch('/api/v1/me/settings', body: body);
      return true;
    } catch (e) {
      debugPrint('Error updating settings: $e');
      return false;
    }
  }
}
