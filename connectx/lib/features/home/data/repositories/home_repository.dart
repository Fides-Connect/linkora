import 'package:flutter/foundation.dart';
import '../../../../services/api_service.dart';
import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../mock_home_data.dart';

class HomeRepository {
  final ApiService _apiService;

  late List<ServiceRequest> _localMockRequests;
  late List<SupporterProfile> _localMockFavorites;
  late SupporterProfile _localMockSupporterProfile;

  HomeRepository({ApiService? apiService})
      : _apiService = apiService ?? ApiService() {
    _localMockRequests = List.from(mockRequests);
    _localMockFavorites = List.from(mockFavorites);
    _localMockSupporterProfile = mockSupporterProfile;
  }

  /// Fetches the list of incoming and outgoing service requests.
  /// Wraps API call to `GET /requests`.
  Future<List<ServiceRequest>> getRequests() async {
    try {
      final data = await _apiService.get('/requests');
      if (data is List) {
        return data.map((json) => ServiceRequest.fromJson(json)).toList();
      }
    } catch (e) {
      debugPrint('API failed for getRequests (using mock data): $e');
    }
    
    // Fallback if API fails or is not implemented
    await Future.delayed(const Duration(milliseconds: 500));
    return _localMockRequests;
  }

  /// Fetches the current user's favorite supporters.
  /// Used in the Favorites Tab.
  /// Wraps API call to `GET /favorites`.
  Future<List<SupporterProfile>> getFavorites() async {
    try {
      final data = await _apiService.get('/favorites');
      if (data is List) {
        return data.map((json) => SupporterProfile.fromJson(json)).toList();
      }
    } catch (e) {
      debugPrint('API failed for getFavorites (using mock data): $e');
    }
    
    // Fallback if API fails or is not implemented
    await Future.delayed(const Duration(milliseconds: 500));
    return _localMockFavorites;
  }

  /// Adds a supporter to favorites.
  /// Wraps API call to `POST /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<SupporterProfile>> addFavorite(SupporterProfile profile) async {
    try {
      await _apiService.post('/favorites/${Uri.encodeComponent(profile.id)}'); 
      return getFavorites();
    } catch (e) {
      debugPrint('API failed for addFavorite (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 200));
      if (!_localMockFavorites.any((p) => p.id == profile.id)) {
        _localMockFavorites.add(profile);
      }
      return _localMockFavorites;
    }
  }

  /// Removes a supporter from favorites.
  /// Wraps API call to `DELETE /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<SupporterProfile>> removeFavorite(SupporterProfile profile) async {
    try {
      await _apiService.delete('/favorites/${Uri.encodeComponent(profile.id)}');
      return getFavorites();
    } catch (e) {
      debugPrint('API failed for removeFavorite (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 200));
      _localMockFavorites.removeWhere((p) => p.id == profile.id);
      return _localMockFavorites;
    }
  }

  /// Fetches the logged-in user's own supporter profile.
  /// Wraps API call to `GET /profile`.
  Future<SupporterProfile> getSupporterProfile() async {
    try {
      final data = await _apiService.get('/profile');
      // If data is null (empty body), we should also fall back
      if (data != null) {
        return SupporterProfile.fromJson(data);
      }
    } catch (e) {
      debugPrint('API failed for getSupporterProfile (using mock data): $e');
    }
    
    // Fallback if API fails or is not implemented
    await Future.delayed(const Duration(milliseconds: 500));
    return _localMockSupporterProfile;
  }

  /// Updates the logged-in user's entire profile.
  /// Wraps API call to `PUT /profile`.
  /// Returns the updated profile.
  Future<SupporterProfile> updateSupporterProfile(SupporterProfile profile) async {
     try {
      await _apiService.put('/profile', body: profile.toJson());
      // Return the profile we just sent, assuming success
      return profile;
    } catch (e) {
      debugPrint('API failed for updateSupporterProfile (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 500));
      _localMockSupporterProfile = profile;
      return _localMockSupporterProfile;
    }
  }

  /// Adds a single competence tag to the user's profile.
  /// Wraps API call to `POST /profile/competencies`.
  /// Returns the updated profile.
  Future<SupporterProfile> addCompetence(String competence) async {
    try {
      await _apiService.post('/profile/competencies', body: {'competence': competence});
      // Fetch fresh profile from server
      return getSupporterProfile();
    } catch (e) {
       debugPrint('API failed for addCompetence (using mock data): $e');
       // Fallback
       await Future.delayed(const Duration(milliseconds: 200));
       if (!_localMockSupporterProfile.competencies.contains(competence)) {
         final updatedCompetencies = List<String>.from(_localMockSupporterProfile.competencies)..add(competence);
         _localMockSupporterProfile = SupporterProfile(
           id: _localMockSupporterProfile.id,
           name: _localMockSupporterProfile.name,
           introduction: _localMockSupporterProfile.introduction,
           competencies: updatedCompetencies,
           averageRating: _localMockSupporterProfile.averageRating,
           reviewCount: _localMockSupporterProfile.reviewCount,
           positiveFeedback: _localMockSupporterProfile.positiveFeedback,
           negativeFeedback: _localMockSupporterProfile.negativeFeedback
         );
       }
       return _localMockSupporterProfile;
    }
  }

  /// Removes a single competence tag from the user's profile.
  /// Wraps API call to `DELETE /profile/competencies/{competence}`.
  /// Returns the updated profile.
  Future<SupporterProfile> removeCompetence(String competence) async {
    try {
      // Assuming RESTful design: /profile/competencies/Gardening
      await _apiService.delete('/profile/competencies/${Uri.encodeComponent(competence)}');
      // Fetch fresh profile from server
      return getSupporterProfile();
    } catch (e) {
       debugPrint('API failed for removeCompetence (using mock data): $e');
       // Fallback
       await Future.delayed(const Duration(milliseconds: 200));
       if (_localMockSupporterProfile.competencies.contains(competence)) {
         final updatedCompetencies = List<String>.from(_localMockSupporterProfile.competencies)..remove(competence);
         _localMockSupporterProfile = SupporterProfile(
           id: _localMockSupporterProfile.id,
           name: _localMockSupporterProfile.name,
           introduction: _localMockSupporterProfile.introduction,
           competencies: updatedCompetencies,
           averageRating: _localMockSupporterProfile.averageRating,
           reviewCount: _localMockSupporterProfile.reviewCount,
           positiveFeedback: _localMockSupporterProfile.positiveFeedback,
           negativeFeedback: _localMockSupporterProfile.negativeFeedback
         );
       }
       return _localMockSupporterProfile;
    }
  }

  /// Fetches proper public profile for another user (e.g. a request sender).
  /// Wraps API call to `GET /users/{id}/profile`.
  Future<SupporterProfile?> getOtherProfile(String userId) async {
    try {
       final data = await _apiService.get('/users/${Uri.encodeComponent(userId)}/profile');
      if (data != null) {
        return SupporterProfile.fromJson(data);
      }
    } catch (e) {
       debugPrint('API failed for getOtherProfile (using mock data): $e');
    }

    // Fallback logic moved from RequestDetailPage
    await Future.delayed(const Duration(milliseconds: 500));

    // Try to find a request by this user to determine which mock profile to return
    // In a real app, we would look up by userId directly.
    // Here we use the name mapping logic that was in UI
    
    // Find request or use defaults
    final request = _localMockRequests.firstWhere(
      (r) => r.userName == userId || r.id == userId, 
      orElse: () => _localMockRequests.first
    );

    if (mockUserProfiles.containsKey(request.userName)) {
      return mockUserProfiles[request.userName];
    }
    
    return null;
  }

  /// Creates a new service request.
  /// Wraps API call to `POST /requests`.
  Future<void> createRequest(ServiceRequest request) async {
    try {
      await _apiService.post('/requests', body: request.toJson());
    } catch (e) {
      debugPrint('API failed for createRequest (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 500));
      _localMockRequests.add(request);
    }
  }

  /// Updates the status (Accepted, Rejected, Completed) of an existing request.
  /// Wraps API call to `PUT /requests/{requestId}/status`.
  Future<void> updateRequestStatus(String requestId, RequestStatus status) async {
    try {
      await _apiService.put('/requests/${Uri.encodeComponent(requestId)}/status', body: {'status': status.name});
    } catch (e) {
       debugPrint('API failed for updateRequestStatus (using mock data): $e');
       // Fallback
       await Future.delayed(const Duration(milliseconds: 200));
       final index = _localMockRequests.indexWhere((r) => r.id == requestId);
       if (index != -1) {
         final original = _localMockRequests[index];
         _localMockRequests[index] = ServiceRequest(
           id: original.id,
           title: original.title,
           amountValue: original.amountValue,
           currency: original.currency,
           startDate: original.startDate,
           endDate: original.endDate,
           userName: original.userName,
           userInitials: original.userInitials,
           category: original.category,
           type: original.type,
           status: status,
           updateText: original.updateText,
           description: original.description,
           location: original.location,
         );
       }
    }
  }
}
