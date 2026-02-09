import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/core/providers/user_provider.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../../helpers/test_helpers.mocks.dart';

void main() {
  UserProvider? userProvider;
  late MockAuthService mockAuthService;
  late MockUser mockUser;
  late StreamController<User?> authStreamController;

  setUp(() {
    mockAuthService = MockAuthService();
    mockUser = MockUser();
    authStreamController = StreamController<User?>();

    // Mock initial calls
    when(mockAuthService.initialize()).thenAnswer((_) async {});
    when(mockAuthService.onCurrentUserChanged).thenAnswer((_) => authStreamController.stream);
  });

  tearDown(() {
    userProvider?.dispose();
    authStreamController.close();
  });

  test('initializes and listens to auth changes', () async {
    userProvider = UserProvider(authService: mockAuthService);
    
    expect(userProvider!.isLoading, true);
    
    // Explicitly call init
    await userProvider!.init();
    
    // Simulate user login
    authStreamController.add(mockUser);
    await Future.delayed(Duration.zero);
    
    expect(userProvider!.user, mockUser);
    expect(userProvider!.isAuthenticated, true);
    expect(userProvider!.isLoading, false);
    
    // Simulate logout
    authStreamController.add(null);
    await Future.delayed(Duration.zero);
    
    expect(userProvider!.user, null);
    expect(userProvider!.isAuthenticated, false);
  });

  test('signInWithGoogle calls auth service', () async {
    userProvider = UserProvider(authService: mockAuthService);
    when(mockAuthService.signInWithGoogle()).thenAnswer((_) async => null);
    
    await userProvider!.signInWithGoogle();
    
    verify(mockAuthService.signInWithGoogle()).called(1);
    expect(userProvider!.isLoading, false);
  });

  test('signOut calls auth service', () async {
    userProvider = UserProvider(authService: mockAuthService);
    when(mockAuthService.signOut()).thenAnswer((_) async {});
    
    await userProvider!.signOut();
    
    verify(mockAuthService.signOut()).called(1);
  });
}
