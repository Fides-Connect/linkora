import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Sets up Firebase mocks at the platform channel level.
/// Must be called before any code that accesses Firebase services.
void setupFirebaseMocks() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // Mock Firebase Core
  const MethodChannel('plugins.flutter.io/firebase_core')
      .setMockMethodCallHandler((MethodCall methodCall) async {
    if (methodCall.method == 'Firebase#initializeCore') {
      return [
        {
          'name': '[DEFAULT]',
          'options': {
            'apiKey': 'test-api-key',
            'appId': 'test-app-id',
            'messagingSenderId': 'test-sender-id',
            'projectId': 'test-project-id',
          },
          'pluginConstants': {},
        }
      ];
    }
    if (methodCall.method == 'Firebase#initializeApp') {
      return {
        'name': methodCall.arguments['appName'],
        'options': methodCall.arguments['options'],
        'pluginConstants': {},
      };
    }
    return null;
  });

  // Mock Firebase Messaging
  const MethodChannel('plugins.flutter.io/firebase_messaging')
      .setMockMethodCallHandler((MethodCall methodCall) async {
    if (methodCall.method == 'Messaging#getToken') {
      return 'mock-fcm-token-12345';
    }
    if (methodCall.method == 'Messaging#requestPermission') {
      return {
        'authorizationStatus': 1, // AuthorizationStatus.authorized
        'alert': true,
        'announcement': false,
        'badge': true,
        'carPlay': false,
        'criticalAlert': false,
        'provisional': false,
        'sound': true,
      };
    }
    if (methodCall.method == 'Messaging#deleteToken') {
      return null;
    }
    return null;
  });

  // Mock Firebase Auth
  const MethodChannel('plugins.flutter.io/firebase_auth')
      .setMockMethodCallHandler((MethodCall methodCall) async {
    if (methodCall.method == 'Auth#registerIdTokenListener') {
      return {
        'name': '[DEFAULT]',
      };
    }
    if (methodCall.method == 'Auth#signOut') {
      return null;
    }
    return null;
  });
}
