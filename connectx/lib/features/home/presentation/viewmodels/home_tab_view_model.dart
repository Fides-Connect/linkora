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
    return _favorites.any((p) => p.name == profile.name);
  }

  Future<void> toggleFavorite(SupporterProfile profile) async {
    if (isFavorite(profile)) {
      await _repository.removeFavorite(profile);
    } else {
      await _repository.addFavorite(profile);
    }
    // Refresh list
    _favorites = await _repository.getFavorites();
    notifyListeners();
  }

  Future<SupporterProfile?> getOtherProfile(String userId) {
    return _repository.getOtherProfile(userId);
  }

  Future<void> updateIntroduction(String introduction) async {
    if (_userProfile == null) return;
    
    final updatedProfile = SupporterProfile(
      name: _userProfile!.name,
      introduction: introduction,
      competencies: _userProfile!.competencies,
      rating: _userProfile!.rating,
      reviewCount: _userProfile!.reviewCount,
      positiveFeedback: _userProfile!.positiveFeedback,
      negativeFeedback: _userProfile!.negativeFeedback
    );

    await _repository.updateSupporterProfile(updatedProfile);
    _userProfile = updatedProfile;
    notifyListeners();
  }

  Future<void> addCompetence(String competence) async {
    if (_userProfile == null) return;
    
    await _repository.addCompetence(competence);
    
    // Optimistic update or fetch again
    // For simplicity, we manually update local state since repository methods usually return void
    // But repository implementation for addCompetence just posts and fallsback.
    // In a real app we might reload the profile or trust the repository updated something if it's shared state.
    // However, the repository methods (as seen before) update the mock data but don't return the new profile.
    
    // Let's reload profile to be safe and consistent with repository
    _userProfile = await _repository.getSupporterProfile();
    notifyListeners();
  }

  Future<void> removeCompetence(String competence) async {
    if (_userProfile == null) return;
    
    await _repository.removeCompetence(competence);
    _userProfile = await _repository.getSupporterProfile();
    notifyListeners();
  }
}
