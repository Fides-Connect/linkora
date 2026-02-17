import '../../../../services/api_service.dart';
import '../../../../models/service_request.dart';
import '../../../../models/user.dart';

class HomeRepository {
  final ApiService _apiService;

  HomeRepository({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  /// Fetches the list of incoming and outgoing service requests.
  /// Wraps API call to `GET /api/v1/service-requests`.
  Future<List<ServiceRequest>> getRequests() async {
    final data = await _apiService.get('/api/v1/service-requests');
    if (data is List) {
      return data.map((json) => ServiceRequest.fromJson(json)).toList();
    }
    return [];
  }

  /// Fetches the current user's favorite users.
  /// Used in the Favorites Tab.
  /// Wraps API call to `GET /api/v1/me/favorites`.
  Future<List<User>> getFavorites() async {
    final data = await _apiService.get('/api/v1/me/favorites');
    if (data is List) {
      return data.map((json) => User.fromJson(json)).toList();
    }
    return [];
  }

  /// Adds a user to favorites.
  /// Wraps API call to `POST /api/v1/me/favorites` with user_id in body.
  /// Returns the updated list of favorites.
  Future<List<User>> addFavorite(User user) async {
    await _apiService.post('/api/v1/me/favorites', body: {'user_id': user.id}); 
    return getFavorites();
  }

  /// Removes a user from favorites.
  /// Wraps API call to `DELETE /api/v1/me/favorites/{user_id}`.
  /// Returns the updated list of favorites.
  Future<List<User>> removeFavorite(User user) async {
    await _apiService.delete('/api/v1/me/favorites/${Uri.encodeComponent(user.id)}');
    return getFavorites();
  }

  /// Fetches the logged-in user's own data.
  /// Wraps API call to `GET /api/v1/me`.
  Future<User> getUser() async {
    final data = await _apiService.get('/api/v1/me');
    return User.fromJson(data);
  }

  /// Updates the logged-in user's entire data.
  /// Wraps API call to `PATCH /api/v1/me`.
  /// Returns the updated user.
  Future<User> updateUser(User user) async {
    final data = await _apiService.patch('/api/v1/me', body: user.toJson());
    // API now returns the full updated user object
    return User.fromJson(data);
  }

  /// Adds a single competence tag to the user.
  /// Wraps API call to `POST /api/v1/me/competencies`.
  /// Returns the updated user.
  Future<User> addCompetence(String competence) async {
    // Create competence object with title field (other fields can be added later)
    final competenceObj = {
      'title': competence,
      'description': '',
      'category': '',
      'price_range': '',
    };
    final data = await _apiService.post('/api/v1/me/competencies', body: {'competence': competenceObj});
    // API returns the updated user object
    return User.fromJson(data);
  }

  /// Removes a single competence tag from the user.
  /// Wraps API call to `DELETE /api/v1/me/competencies/{competence_id}`.
  /// Returns the updated user.
  Future<User> removeCompetence(String competenceId) async {
    final data = await _apiService.delete('/api/v1/me/competencies/${Uri.encodeComponent(competenceId)}');
    // API returns the updated user object
    return User.fromJson(data);
  }

  /// Fetches proper public data for another user (e.g. a request sender).
  /// Wraps API call to `GET /api/v1/users/{user_id}`.
  Future<User?> getOtherUser(String userId) async {
    final data = await _apiService.get('/api/v1/users/${Uri.encodeComponent(userId)}');
    if (data != null) {
      return User.fromJson(data);
    }
    return null;
  }

  /// Adds a new service request.
  /// Wraps API call to `POST /api/v1/service-requests`.
  /// Returns the created service request.
  Future<ServiceRequest> addServiceRequest(ServiceRequest request) async {
    final data = await _apiService.post('/api/v1/service-requests', body: request.toJson());
    return ServiceRequest.fromJson(data);
  }

  /// Updates the status (Accepted, Rejected, Completed) of an existing service request.
  /// Wraps API call to `PATCH /api/v1/service-requests/{requestId}`.
  /// Returns the updated service request.
  Future<ServiceRequest> updateServiceRequestStatus(String requestId, RequestStatus status) async {
    final data = await _apiService.patch('/api/v1/service-requests/${Uri.encodeComponent(requestId)}', body: {'status': status.name});
    return ServiceRequest.fromJson(data);
  }
}
