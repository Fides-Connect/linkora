import 'package:flutter/foundation.dart';
import '../../../../services/api_service.dart';
import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../mock_home_data.dart';

class HomeRepository {
  final ApiService _apiService;

  HomeRepository({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

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
    return mockRequests;
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
    return mockFavorites;
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
    return mockSupporterProfile;
  }

  /// Updates the logged-in user's entire profile.
  /// Wraps API call to `PUT /profile`.
  Future<void> updateSupporterProfile(SupporterProfile profile) async {
     try {
      await _apiService.put('/profile', body: profile.toJson());
      return;
    } catch (e) {
      debugPrint('API failed for updateSupporterProfile (using mock data): $e');
    }

    // Fallback
    await Future.delayed(const Duration(milliseconds: 500));
    mockSupporterProfile = profile;
  }

  /// Adds a single competence tag to the user's profile.
  /// Wraps API call to `POST /profile/competencies`.
  Future<void> addCompetence(String competence) async {
    try {
      await _apiService.post('/profile/competencies', body: {'competence': competence});
      return;
    } catch (e) {
       debugPrint('API failed for addCompetence (using mock data): $e');
    }

    // Fallback
    await Future.delayed(const Duration(milliseconds: 200));
    if (!mockSupporterProfile.competencies.contains(competence)) {
      final updatedCompetencies = List<String>.from(mockSupporterProfile.competencies)..add(competence);
      mockSupporterProfile = SupporterProfile(
        name: mockSupporterProfile.name,
        introduction: mockSupporterProfile.introduction,
        competencies: updatedCompetencies,
        rating: mockSupporterProfile.rating,
        reviewCount: mockSupporterProfile.reviewCount,
        positiveFeedback: mockSupporterProfile.positiveFeedback,
        negativeFeedback: mockSupporterProfile.negativeFeedback
      );
    }
  }

  /// Removes a single competence tag from the user's profile.
  /// Wraps API call to `DELETE /profile/competencies/{competence}`.
  Future<void> removeCompetence(String competence) async {
    try {
      // Assuming RESTful design: /profile/competencies/Gardening
      await _apiService.delete('/profile/competencies/$competence');
      return;
    } catch (e) {
       debugPrint('API failed for removeCompetence (using mock data): $e');
    }

    // Fallback
    await Future.delayed(const Duration(milliseconds: 200));
    if (mockSupporterProfile.competencies.contains(competence)) {
      final updatedCompetencies = List<String>.from(mockSupporterProfile.competencies)..remove(competence);
      mockSupporterProfile = SupporterProfile(
        name: mockSupporterProfile.name,
        introduction: mockSupporterProfile.introduction,
        competencies: updatedCompetencies,
        rating: mockSupporterProfile.rating,
        reviewCount: mockSupporterProfile.reviewCount,
        positiveFeedback: mockSupporterProfile.positiveFeedback,
        negativeFeedback: mockSupporterProfile.negativeFeedback
      );
    }
  }

  /// Fetches proper public profile for another user (e.g. a request sender).
  /// Wraps API call to `GET /users/{id}/profile`.
  Future<SupporterProfile?> getOtherProfile(String userId) async {
    try {
      final data = await _apiService.get('/users/$userId/profile');
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
    final request = mockRequests.firstWhere(
      (r) => r.userName == userId || r.id == userId, 
      orElse: () => mockRequests.first
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
      return;
    } catch (e) {
      debugPrint('API failed for createRequest (using mock data): $e');
    }

    // Fallback
    await Future.delayed(const Duration(milliseconds: 500));
    mockRequests.add(request);
  }

  /// Updates the status (Accepted, Rejected, Completed) of an existing request.
  /// Wraps API call to `PUT /requests/{id}/status`.
  Future<void> updateRequestStatus(String requestId, RequestStatus status) async {
    try {
      await _apiService.put('/requests/$requestId/status', body: {'status': status.name});
      return;
    } catch (e) {
       debugPrint('API failed for updateRequestStatus (using mock data): $e');
    }

    // Fallback
    await Future.delayed(const Duration(milliseconds: 200));
    final index = mockRequests.indexWhere((r) => r.id == requestId);
    if (index != -1) {
      final original = mockRequests[index];
      mockRequests[index] = ServiceRequest(
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
        status: status, // Updated status
        updateText: original.updateText,
        description: original.description,
        location: original.location,
      );
    }
  }
}
