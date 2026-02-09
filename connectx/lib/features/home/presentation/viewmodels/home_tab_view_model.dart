import 'package:flutter/foundation.dart';
import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../../data/repositories/home_repository.dart';

class HomeTabViewModel extends ChangeNotifier {
  final HomeRepository _repository;
  
  List<ServiceRequest> _incomingRequests = [];
  List<ServiceRequest> _outgoingRequests = [];
  List<SupporterProfile> _favorites = [];
  SupporterProfile? _userProfile;
  
  bool _isLoading = false;
  String? _error;

  HomeTabViewModel({HomeRepository? repository}) 
      : _repository = repository ?? HomeRepository();

  List<ServiceRequest> get incomingRequests => _incomingRequests;
  List<ServiceRequest> get outgoingRequests => _outgoingRequests;
  List<SupporterProfile> get favorites => _favorites;
  SupporterProfile? get userProfile => _userProfile;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadData() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final requests = await _repository.getRequests();
      _incomingRequests = requests.where((r) => r.type == RequestType.incoming).toList();
      _outgoingRequests = requests.where((r) => r.type == RequestType.outgoing).toList();
      
      _favorites = await _repository.getFavorites();
      _userProfile = await _repository.getSupporterProfile();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  bool isFavorite(SupporterProfile profile) {
    return _favorites.any((p) => p.id == profile.id);
  }

  Future<void> toggleFavorite(SupporterProfile profile) async {
    try {
      if (isFavorite(profile)) {
        _favorites = await _repository.removeFavorite(profile);
      } else {
        _favorites = await _repository.addFavorite(profile);
      }
      _error = null;
    } catch (e) {
      _error = 'Failed to update favorites: $e';
    }
    notifyListeners();
  }

  Future<SupporterProfile?> getOtherProfile(String userId) {
    return _repository.getOtherProfile(userId);
  }

  Future<void> updateIntroduction(String introduction) async {
    if (_userProfile == null) return;
    
    final updatedProfile = SupporterProfile(
      id: _userProfile!.id,
      name: _userProfile!.name,
      introduction: introduction,
      competencies: _userProfile!.competencies,
      rating: _userProfile!.rating,
      reviewCount: _userProfile!.reviewCount,
      positiveFeedback: _userProfile!.positiveFeedback,
      negativeFeedback: _userProfile!.negativeFeedback
    );

    try {
      // Use the profile returned by the repository to ensure consistency
      _userProfile = await _repository.updateSupporterProfile(updatedProfile);
      _error = null;
    } catch (e) {
      _error = 'Failed to update profile: $e';
    }
    notifyListeners();
  }

  Future<void> addCompetence(String competence) async {
    if (_userProfile == null) return;
    
    try {
      _userProfile = await _repository.addCompetence(competence);
      _error = null;
    } catch (e) {
      _error = 'Failed to add competence: $e';
    }
    notifyListeners();
  }

  Future<void> removeCompetence(String competence) async {
    if (_userProfile == null) return;
    
    try {
      _userProfile = await _repository.removeCompetence(competence);
      _error = null;
    } catch (e) {
      _error = 'Failed to remove competence: $e';
    }
    notifyListeners();
  }
}
