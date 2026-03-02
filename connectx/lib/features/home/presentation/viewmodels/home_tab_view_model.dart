import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../../../models/service_request.dart';
import '../../../../models/user.dart';
import '../../data/repositories/home_repository.dart';

class HomeTabViewModel extends ChangeNotifier {
  final HomeRepository _repository;

  StreamSubscription<void>? _requestsWatchSubscription;

  List<ServiceRequest> _incomingRequests = [];
  List<ServiceRequest> _outgoingRequests = [];
  List<User> _favorites = [];
  User? _user;

  bool _isLoading = false;
  bool _isReloading = false;
  String? _error;

  HomeTabViewModel({HomeRepository? repository})
      : _repository = repository ?? HomeRepository();

  @override
  void dispose() {
    _requestsWatchSubscription?.cancel();
    super.dispose();
  }

  List<ServiceRequest> get incomingRequests => _incomingRequests;
  List<ServiceRequest> get outgoingRequests => _outgoingRequests;
  List<User> get favorites => _favorites;
  User? get user => _user;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadData() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _user = await _repository.getUser();
      _startWatchingRequests();

      final requests = await _repository.getRequests();
      final currentUserId = _user?.id ?? '';
      _incomingRequests = requests.where((r) => r.getType(currentUserId) == RequestType.incoming).toList();
      _outgoingRequests = requests.where((r) => r.getType(currentUserId) == RequestType.outgoing).toList();

      _favorites = await _repository.getFavorites();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void _startWatchingRequests() {
    _requestsWatchSubscription?.cancel();
    final userId = _user?.id;
    if (userId == null || userId.isEmpty) return;

    _requestsWatchSubscription = _repository
        .watchServiceRequests(userId)
        .listen(
          (_) => _reloadRequests(),
          onError: (Object e) {
            _error = 'Firestore watch error: $e';
            notifyListeners();
          },
        );
  }

  Future<void> _reloadRequests() async {
    if (_isLoading || _isReloading) return;
    _isReloading = true;
    try {
      final requests = await _repository.getRequests();
      final currentUserId = _user?.id ?? '';
      _incomingRequests = requests
          .where((r) => r.getType(currentUserId) == RequestType.incoming)
          .toList();
      _outgoingRequests = requests
          .where((r) => r.getType(currentUserId) == RequestType.outgoing)
          .toList();
      _error = null;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    } finally {
      _isReloading = false;
    }
  }

  bool isFavorite(User user) {
    return _favorites.any((p) => p.id == user.id);
  }

  Future<void> toggleFavorite(User user) async {
    try {
      if (isFavorite(user)) {
        _favorites = await _repository.removeFavorite(user);
      } else {
        _favorites = await _repository.addFavorite(user);
      }
      _error = null;
    } catch (e) {
      _error = 'Failed to update favorites: $e';
    }
    notifyListeners();
  }

  /// Finds a service request by ID from either the incoming or outgoing list.
  /// Returns null if not found (e.g. request was deleted).
  ServiceRequest? findRequest(String id) {
    try {
      return [..._incomingRequests, ..._outgoingRequests]
          .firstWhere((r) => r.serviceRequestId == id);
    } catch (_) {
      return null;
    }
  }

  Future<User?> getOtherUser(String userId) {
    return _repository.getOtherUser(userId);
  }

  Future<void> updateServiceRequestStatus(
    ServiceRequest request,
    RequestStatus newStatus,
  ) async {
    try {
      await _repository.updateServiceRequestStatus(request.serviceRequestId, newStatus);
      await _reloadRequests();
    } catch (e) {
      _error = 'Failed to update status: $e';
      notifyListeners();
      rethrow;
    }
  }

  Future<void> updateIntroduction(String introduction) async {
    if (_user == null) return;
    
    final updatedUser = _user!.copyWith(selfIntroduction: introduction);

    try {
      // Use the user returned by the repository to ensure consistency
      _user = await _repository.updateUser(updatedUser);
      _error = null;
    } catch (e) {
      _error = 'Failed to update user: $e';
    }
    notifyListeners();
  }

  Future<void> addCompetence(String competence) async {
    if (_user == null) return;
    
    try {
      _user = await _repository.addCompetence(competence);
      _error = null;
    } catch (e) {
      _error = 'Failed to add competence: $e';
    }
    notifyListeners();
  }

  Future<void> removeCompetence(String competence) async {
    if (_user == null) return;
    
    try {
      _user = await _repository.removeCompetence(competence);
      _error = null;
    } catch (e) {
      _error = 'Failed to remove competence: $e';
    }
    notifyListeners();
  }
}
