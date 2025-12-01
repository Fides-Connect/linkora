import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'package:connectx/services/user_service.dart';
import 'dart:convert';
import '../test_helpers/firebase_mocks.dart';

// Generate mocks
@GenerateMocks([User, http.Client, UserMetadata])
import 'user_service_test.mocks.dart';

void main() {
  setupFirebaseMocks();

  group('UserService', () {
    late UserService userService;
    late MockUser mockUser;
    late MockClient mockClient;
    late MockUserMetadata mockUserMetadata;

    setUp(() {
      userService = UserService();
      mockUser = MockUser();
      mockClient = MockClient();
      mockUserMetadata = MockUserMetadata();
    });

    tearDown(() {
      // Clear any stored data between tests
      userService.clearUserData();
    });

    test('should instantiate successfully', () {
      expect(userService, isNotNull);
      expect(userService.fcmToken, isNull);
      expect(userService.userProfile, isNull);
    });

    test('initializeFCM should handle Firebase not being available', () async {
      // In test environment without full Firebase initialization,
      // initializeFCM should catch errors and not crash
      await userService.initializeFCM();
      
      // FCM token will be null since Firebase isn't fully initialized in tests
      // but the method should complete without throwing
      expect(userService.fcmToken, isNull);
    });

    test('clearUserData should clear user profile and FCM token', () {
      userService.clearUserData();
      
      expect(userService.userProfile, isNull);
      expect(userService.fcmToken, isNull);
    });

    group('syncUserWithBackend', () {
      setUp(() {
        when(mockUser.uid).thenReturn('test_user_123');
        when(mockUser.email).thenReturn('test@example.com');
        when(mockUser.displayName).thenReturn('Test User');
        when(mockUser.photoURL).thenReturn('https://example.com/photo.jpg');
        when(mockUser.getIdToken()).thenAnswer((_) async => 'mock_id_token');
        when(mockUser.metadata).thenReturn(mockUserMetadata);
        when(mockUserMetadata.creationTime).thenReturn(DateTime(2024, 1, 1));
        when(mockUserMetadata.lastSignInTime).thenReturn(DateTime(2024, 12, 1));
      });

      test('should return true on successful sync for new user', () async {
        // Mock successful HTTP response with proper backend format
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenAnswer((_) async => http.Response(
          json.encode({
            'success': true,
            'message': 'User synced',
            'user_id': 'test_user_123',
            'is_new_user': true,
            'user_profile': {
              'uid': 'test_user_123',
              'email': 'test@example.com',
              'name': 'Test User',
            },
          }),
          200,
        ));

        final result = await userService.syncUserWithBackend(
          mockUser,
          client: mockClient,
          serverUrl: 'http://localhost:8080',
        );

        expect(result, isTrue);
        expect(userService.userProfile, isNotNull);
        expect(userService.userProfile!['uid'], equals('test_user_123'));
        
        // Verify HTTP call was made
        verify(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).called(1);
      });

      test('should return false when server URL not configured', () async {
        final result = await userService.syncUserWithBackend(
          mockUser,
          client: mockClient,
          serverUrl: null,
        );

        expect(result, isFalse);
        verifyNever(mockClient.post(any, headers: anyNamed('headers'), body: anyNamed('body')));
      });

      test('should return false on network timeout', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenThrow(Exception('Connection timeout'));

        final result = await userService.syncUserWithBackend(
          mockUser,
          client: mockClient,
          serverUrl: 'http://localhost:8080',
        );

        expect(result, isFalse);
      });

      test('should return false on HTTP error status', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenAnswer((_) async => http.Response(
          json.encode({'error': 'Server error'}),
          500,
        ));

        final result = await userService.syncUserWithBackend(
          mockUser,
          client: mockClient,
          serverUrl: 'http://localhost:8080',
        );

        expect(result, isFalse);
      });

      test('should handle non-200 status codes gracefully', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenAnswer((_) async => http.Response('', 404));

        final result = await userService.syncUserWithBackend(
          mockUser,
          client: mockClient,
          serverUrl: 'http://localhost:8080',
        );

        expect(result, isFalse);
      });
    });

    group('notifyLogout', () {
      setUp(() {
        when(mockUser.uid).thenReturn('logout_user');
        when(mockUser.email).thenReturn('logout@example.com');
        when(mockUser.getIdToken()).thenAnswer((_) async => 'logout_token');
      });

      test('should complete without error on successful logout', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenAnswer((_) async => http.Response(
          json.encode({'success': true}),
          200,
        ));

        await expectLater(
          userService.notifyLogout(
            mockUser,
            client: mockClient,
            serverUrl: 'http://localhost:8080',
          ),
          completes,
        );

        verify(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).called(1);
      });

      test('should handle network errors gracefully', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenThrow(Exception('Network error'));

        // Should not throw, just log error
        await expectLater(
          userService.notifyLogout(
            mockUser,
            client: mockClient,
            serverUrl: 'http://localhost:8080',
          ),
          completes,
        );
      });

      test('should handle timeout gracefully', () async {
        when(mockClient.post(
          any,
          headers: anyNamed('headers'),
          body: anyNamed('body'),
        )).thenThrow(Exception('Request timeout'));

        await expectLater(
          userService.notifyLogout(
            mockUser,
            client: mockClient,
            serverUrl: 'http://localhost:8080',
          ),
          completes,
        );
      });

      test('should skip notification when server URL is null', () async {
        await userService.notifyLogout(
          mockUser,
          client: mockClient,
          serverUrl: null,
        );

        verifyNever(mockClient.post(any, headers: anyNamed('headers'), body: anyNamed('body')));
      });
    });
  });
}
