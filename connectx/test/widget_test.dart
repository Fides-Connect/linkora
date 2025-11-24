// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:connectx/services/auth_service.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:connectx/main.dart';

void main() {
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
