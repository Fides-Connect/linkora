import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:connectx/services/auth_service.dart';
import 'package:connectx/services/user_service.dart';

// Generate mocks
@GenerateMocks([FirebaseAuth, GoogleSignIn, UserService, UserCredential, User])
import 'auth_service_test.mocks.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthService', () {
    late AuthService authService;
    late MockUser mockUser;

    setUp(() {
      authService = AuthService();
      mockUser = MockUser();
    });

    test('should instantiate successfully', () {
      expect(authService, isNotNull);
    });

    group('Mock User objects', () {
      test('should work with mock User properties', () {
        when(mockUser.uid).thenReturn('mock_uid_123');
        when(mockUser.email).thenReturn('test@example.com');
        when(mockUser.displayName).thenReturn('Test User');
        when(mockUser.photoURL).thenReturn('https://example.com/photo.jpg');
        
        expect(mockUser.uid, equals('mock_uid_123'));
        expect(mockUser.email, equals('test@example.com'));
        expect(mockUser.displayName, equals('Test User'));
        expect(mockUser.photoURL, equals('https://example.com/photo.jpg'));
      });

      test('should work with async methods like getIdToken', () async {
        when(mockUser.getIdToken()).thenAnswer((_) async => 'mock_token_xyz');
        
        final token = await mockUser.getIdToken();
        expect(token, equals('mock_token_xyz'));
        
        verify(mockUser.getIdToken()).called(1);
      });
    });

    group('Mock setup verification', () {
      test('UserCredential mock should work', () {
        final mockCredential = MockUserCredential();
        when(mockCredential.user).thenReturn(mockUser);
        when(mockUser.uid).thenReturn('user_from_credential');
        
        expect(mockCredential.user, isNotNull);
        expect(mockCredential.user!.uid, equals('user_from_credential'));
      });
    });
  });
}
