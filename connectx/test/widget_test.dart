// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:connectx/services/auth_service.dart';
import 'package:firebase_core_platform_interface/firebase_core_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:connectx/main.dart';

// Mock Firebase Core platform
class MockFirebaseCore extends FirebasePlatform {
  @override
  FirebaseAppPlatform app([String name = defaultFirebaseAppName]) {
    return MockFirebaseApp();
  }

  @override
  Future<FirebaseAppPlatform> initializeApp({
    String? name,
    FirebaseOptions? options,
  }) async {
    return MockFirebaseApp();
  }

  @override
  List<FirebaseAppPlatform> get apps => [MockFirebaseApp()];
}

class MockFirebaseApp extends FirebaseAppPlatform {
  MockFirebaseApp() : super('test-app', const FirebaseOptions(
    apiKey: 'test-api-key',
    appId: 'test-app-id',
    messagingSenderId: 'test-sender-id',
    projectId: 'test-project-id',
  ));

  @override
  bool get isAutomaticDataCollectionEnabled => false;

  @override
  Future<void> delete() async {}

  @override
  Future<void> setAutomaticDataCollectionEnabled(bool enabled) async {}

  @override
  Future<void> setAutomaticResourceManagementEnabled(bool enabled) async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    // Setup Firebase mock for testing
    FirebasePlatform.instance = MockFirebaseCore();
  });

  testWidgets('ConnectX app smoke test', (WidgetTester tester) async {

    // Create AuthService
    final auth = AuthService();

    // Build our app
    await tester.pumpWidget(ConnectXApp(auth: auth));

    // Pump once more to allow localization to load and widget tree to build
    await tester.pump();

    // Verify that our app loads with the correct title.
    expect(find.text('Welcome to Fides'), findsOneWidget);
  });
}
