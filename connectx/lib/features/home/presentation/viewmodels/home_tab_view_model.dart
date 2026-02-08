import 'package:flutter/foundation.dart';
import '../../../../models/service_request.dart';
import '../../../../models/user.dart';
import '../../data/repositories/home_repository.dart';

class HomeTabViewModel extends ChangeNotifier {
  final HomeRepository _repository;
  
  List<ServiceRequest> _incomingRequests = [];
  List<ServiceRequest> _outgoingRequests = [];
  List<User> _favorites = [];
  User? _user;
  
  bool _isLoading = false;
  String? _error;

  HomeTabViewModel({HomeRepository? repository}) 
      : _repository = repository ?? HomeRepository();

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
      final requests = await _repository.getRequests();
      
      // Use getType() method with current user's ID to determine request type
      final currentUserId = _user?.userId ?? '';
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

  bool isFavorite(User user) {
    return _favorites.any((p) => p.userId == user.userId);
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

  Future<User?> getOtherUser(String userId) {
    return _repository.getOtherUser(userId);
  }

  Future<void> updateIntroduction(String introduction) async {
    if (_user == null) return;
    
    final updatedUser = _user!.copyWith(introduction: introduction);

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
