import 'dart:convert';
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart'; // Import FirebaseAuth to use MockFirebaseAuth
import 'package:connectx/services/api_service.dart';
import '../helpers/test_helpers.mocks.dart';

void main() {
  late ApiService apiService;
  late MockFirebaseAuthWrapper mockAuth;
  late MockClient mockClient;
  late MockUser mockUser;

  setUp(() async {
    mockAuth = MockFirebaseAuthWrapper();
    mockClient = MockClient();
    mockUser = MockUser();

    // Setup generic mock user
    when(mockAuth.currentUser).thenReturn(mockUser);
    when(mockUser.getIdToken()).thenAnswer((_) async => 'fake_token');
    
    apiService = ApiService(
      auth: mockAuth, 
      client: mockClient,
      baseUrl: 'http://test.com'
    );
  });

  group('ApiService', () {
    test('get performs a GET request', () async {
      // Arrange
      when(mockAuth.currentUser).thenReturn(mockUser);
      when(mockUser.getIdToken()).thenAnswer((_) async => 'fake_token');
      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenAnswer((_) async => http.Response('{"key": "value"}', 200));

      // Act
      final result = await apiService.get('/test');

      // Assert
      expect(result, {'key': 'value'});
      verify(mockClient.get(
        Uri.parse('http://test.com/test'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer fake_token',
        },
      )).called(1);
    });

    test('post performs a POST request with body', () async {
      // Arrange
      when(mockAuth.currentUser).thenReturn(mockUser);
      when(mockUser.getIdToken()).thenAnswer((_) async => 'fake_token');
      when(mockClient.post(any, headers: anyNamed('headers'), body: anyNamed('body')))
          .thenAnswer((_) async => http.Response('{"user_id": 1}', 201));

      // Act
      final result = await apiService.post('/test', body: {'name': 'data'});

      // Assert
      expect(result, {'user_id': 1});
      verify(mockClient.post(
        Uri.parse('http://test.com/test'),
        headers: anyNamed('headers'),
        body: jsonEncode({'name': 'data'}),
      )).called(1);
    });

    test('handles 404 error', () async {
       // Arrange
      when(mockAuth.currentUser).thenReturn(null);
      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenAnswer((_) async => http.Response('Not Found', 404));

      // Act & Assert
      await expectLater(apiService.get('/unknown'), throwsA(isA<ApiException>()));

      // Verify request was made with expected headers (no auth token)
      verify(mockClient.get(
        Uri.parse('http://test.com/unknown'),
        headers: {
          'Content-Type': 'application/json',
        },
      )).called(1);
    });

    test('handles request timeout', () async {
      // Arrange
      when(mockAuth.currentUser).thenReturn(mockUser);
      when(mockUser.getIdToken()).thenAnswer((_) async => 'fake_token');
      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenThrow(TimeoutException('Request timed out')); // Simulate timeout from client

      // Act & Assert
      // We expect ApiException with specific message or just ApiException
      expect(
        () async => await apiService.get('/slow'),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', contains('timed out'))),
      );
    });

    test('handles malformed JSON response', () async {
      // Arrange
      when(mockAuth.currentUser).thenReturn(mockUser);
      // Return 200 OK but with HTML body (e.g. proxy error page)
      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenAnswer((_) async => http.Response('<html>Error</html>', 200));

      // Act
      final result = await apiService.get('/bad_json');

      // Assert
      // The implemented logic returns raw body if jsonDecode fails
      expect(result, '<html>Error</html>'); 
    });
  });
}
