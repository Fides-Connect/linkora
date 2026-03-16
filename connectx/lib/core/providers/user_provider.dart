import 'dart:async';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../../services/auth_service.dart';

class UserProvider extends ChangeNotifier {
  final AuthService _authService;
  User? _user;
  bool _isLoading = true;
  String? _error;
  StreamSubscription<User?>? _authSubscription;

  User? get user => _user;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isAuthenticated => _user != null;

  UserProvider({AuthService? authService}) 
      : _authService = authService ?? AuthService();
  
  Future<void> init() async {
    try {
      await _authService.initialize();
      _authSubscription = _authService.onCurrentUserChanged.listen((user) async {
        if (user != null) {
          // Stay in loading state while we sync — home page must not build
          // before the user document exists in Firestore (race → 404 on /me).
          _isLoading = true;
          notifyListeners();
          try {
            await _authService.performSyncAndConnect(user);
          } catch (e) {
            debugPrint('[UserProvider] sync/connect error (non-fatal): $e');
          }
        }
        _user = user;
        _isLoading = false;
        notifyListeners();
      });
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> signInWithGoogle() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      await _authService.signInWithGoogle();
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> signOut() async {
    _isLoading = true;
    notifyListeners();
    await _authService.signOut();
    _isLoading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    super.dispose();
  }
}
