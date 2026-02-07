import 'package:flutter/foundation.dart';
import '../../../../services/api_service.dart';
import '../../../../models/service_request.dart';
import '../../../../models/user.dart';
import '../mock_home_data.dart';

class HomeRepository {
  final ApiService _apiService;

  late List<ServiceRequest> _localMockRequests;
  late List<User> _localMockFavorites;
  late User _localMockUser;

  HomeRepository({ApiService? apiService})
      : _apiService = apiService ?? ApiService() {
    _localMockRequests = List.from(mockRequests);
    _localMockFavorites = List.from(mockFavorites);
    _localMockUser = mockUser;
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

  /// Fetches the current user's favorite user IDs.
  /// Used in the Favorites Tab.
  /// Wraps API call to `GET /favorites`.
  Future<List<User>> getFavorites() async {
    try {
      final data = await _apiService.get('/favorites');
      if (data is List) {
        return data.map((json) => User.fromJson(json)).toList();
      }
    } catch (e) {
      debugPrint('API failed for getFavorites (using mock data): $e');
    }
    
    // Fallback if API fails or is not implemented
    await Future.delayed(const Duration(milliseconds: 500));
    return _localMockFavorites;
  }

  /// Adds a user to favorites.
  /// Wraps API call to `POST /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<User>> addFavorite(User user) async {
    try {
      await _apiService.post('/favorites/${Uri.encodeComponent(user.userId)}'); 
      return getFavorites();
    } catch (e) {
      debugPrint('API failed for addFavorite (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 200));
      if (!_localMockFavorites.any((p) => p.userId == user.userId)) {
        _localMockFavorites.add(user);
      }
      return _localMockFavorites;
    }
  }

  /// Removes a user from favorites.
  /// Wraps API call to `DELETE /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<User>> removeFavorite(User user) async {
    try {
      await _apiService.delete('/favorites/${Uri.encodeComponent(user.userId)}');
      return getFavorites();
    } catch (e) {
      debugPrint('API failed for removeFavorite (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 200));
      _localMockFavorites.removeWhere((p) => p.userId == user.userId);
      return _localMockFavorites;
    }
  }

  /// Fetches the logged-in user's own data.
  /// Wraps API call to `GET /data`.
  Future<User> getUser() async {
    try {
      final data = await _apiService.get('/user');
      // If data is null (empty body), we should also fall back
      if (data != null) {
        return User.fromJson(data);
      }
    } catch (e) {
      debugPrint('API failed for getUser (using mock data): $e');
    }
    
    // Fallback if API fails or is not implemented
    await Future.delayed(const Duration(milliseconds: 500));
    return _localMockUser;
  }

  /// Updates the logged-in user's entire data.
  /// Wraps API call to `PUT /user`.
  /// Returns the updated user.
  Future<User> updateUser(User user) async {
     try {
      await _apiService.put('/user', body: user.toJson());
      // Return the user we just sent, assuming success
      return user;
    } catch (e) {
      debugPrint('API failed for updateUser (using mock data): $e');
      // Fallback
      await Future.delayed(const Duration(milliseconds: 500));
      _localMockUser = user;
      return _localMockUser;
    }
  }

  /// Adds a single competence tag to the user.
  /// Wraps API call to `POST /user/competencies`.
  /// Returns the updated user.
  Future<User> addCompetence(String competence) async {
    try {
      // Create competence object with title field (other fields can be added later)
      final competenceObj = {
        'title': competence,
        'description': '',
        'category': '',
        'price_range': '',
      };
      await _apiService.post('/user/competencies', body: {'competence': competenceObj});
      // Fetch fresh user from server
      return getUser();
    } catch (e) {
       debugPrint('API failed for addCompetence (using mock data): $e');
       // Fallback
       await Future.delayed(const Duration(milliseconds: 200));
       if (!_localMockUser.competencies.contains(competence)) {
         final updatedCompetencies = List<String>.from(_localMockUser.competencies)..add(competence);
         _localMockUser = User(
           userId: _localMockUser.userId,
           name: _localMockUser.name,
           introduction: _localMockUser.introduction,
           competencies: updatedCompetencies,
           averageRating: _localMockUser.averageRating,
           reviewCount: _localMockUser.reviewCount,
           positiveFeedback: _localMockUser.positiveFeedback,
           negativeFeedback: _localMockUser.negativeFeedback
         );
       }
       return _localMockUser;
    }
  }

  /// Removes a single competence tag from the user.
  /// Wraps API call to `DELETE /user/competencies/{competence}`.
  /// Returns the updated user.
  Future<User> removeCompetence(String competence) async {
    try {
      // Assuming RESTful design: /user/competencies/Gardening
      await _apiService.delete('/user/competencies/${Uri.encodeComponent(competence)}');
      // Fetch fresh user from server
      return getUser();
    } catch (e) {
       debugPrint('API failed for removeCompetence (using mock data): $e');
       // Fallback
       await Future.delayed(const Duration(milliseconds: 200));
       if (_localMockUser.competencies.contains(competence)) {
         final updatedCompetencies = List<String>.from(_localMockUser.competencies)..remove(competence);
         _localMockUser = User(
           userId: _localMockUser.userId,
           name: _localMockUser.name,
           introduction: _localMockUser.introduction,
           competencies: updatedCompetencies,
           averageRating: _localMockUser.averageRating,
           reviewCount: _localMockUser.reviewCount,
           positiveFeedback: _localMockUser.positiveFeedback,
           negativeFeedback: _localMockUser.negativeFeedback
         );
       }
       return _localMockUser;
    }
  }

  /// Fetches proper public data for another user (e.g. a request sender).
  /// Wraps API call to `GET /users/{id}/user`.
  Future<User?> getOtherUser(String userId) async {
    try {
       final data = await _apiService.get('/users/${Uri.encodeComponent(userId)}/user');
      if (data != null) {
        return User.fromJson(data);
      }
    } catch (e) {
       debugPrint('API failed for getOtherUser (using mock data): $e');
    }

    // Fallback logic moved from RequestDetailPage
    await Future.delayed(const Duration(milliseconds: 500));

    // Try to find a request by this user ID to determine which mock user to return
    // In a real app, we would look up by userId directly.
    
    // Find request where the userId matches seeker or provider
    final request = _localMockRequests.firstWhere(
      (r) => r.seekerUserId == userId || r.selectedProviderUserId == userId || r.service_request_id == userId, 
      orElse: () => _localMockRequests.first
    );

    // Try to match with seeker or provider names
    final userName = request.seekerUserId == userId ? request.seekerUserName : request.selectedProviderUserName;
    if (mockUsers.containsKey(userName)) {
      return mockUsers[userName];
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
       final index = _localMockRequests.indexWhere((r) => r.service_request_id == requestId);
       if (index != -1) {
         final original = _localMockRequests[index];
         _localMockRequests[index] = ServiceRequest(
           service_request_id: original.service_request_id,
           title: original.title,
           amountValue: original.amountValue,
           currency: original.currency,
           startDate: original.startDate,
           endDate: original.endDate,
           seekerUserId: original.seekerUserId,
           seekerUserName: original.seekerUserName,
           seekerUserInitials: original.seekerUserInitials,
           selectedProviderUserId: original.selectedProviderUserId,
           selectedProviderUserName: original.selectedProviderUserName,
           selectedProviderUserInitials: original.selectedProviderUserInitials,
           category: original.category,
           status: status,
           updateText: original.updateText,
           description: original.description,
           location: original.location,
         );
       }
    }
  }
}
