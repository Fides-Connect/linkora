import '../../../../services/api_service.dart';
import '../../../../models/service_request.dart';
import '../../../../models/user.dart';

class HomeRepository {
  final ApiService _apiService;

  HomeRepository({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  /// Fetches the list of incoming and outgoing service requests.
  /// Wraps API call to `GET /service_requests`.
  Future<List<ServiceRequest>> getRequests() async {
    final data = await _apiService.get('/service_requests');
    if (data is List) {
      return data.map((json) => ServiceRequest.fromJson(json)).toList();
    }
    return [];
  }

  /// Fetches the current user's favorite user IDs.
  /// Used in the Favorites Tab.
  /// Wraps API call to `GET /favorites`.
  Future<List<User>> getFavorites() async {
    final data = await _apiService.get('/favorites');
    if (data is List) {
      return data.map((json) => User.fromJson(json)).toList();
    }
    return [];
  }

  /// Adds a user to favorites.
  /// Wraps API call to `POST /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<User>> addFavorite(User user) async {
    await _apiService.post('/favorites/${Uri.encodeComponent(user.userId)}'); 
    return getFavorites();
  }

  /// Removes a user from favorites.
  /// Wraps API call to `DELETE /favorites/{id}`.
  /// Returns the updated list of favorites.
  Future<List<User>> removeFavorite(User user) async {
    await _apiService.delete('/favorites/${Uri.encodeComponent(user.userId)}');
    return getFavorites();
  }

  /// Fetches the logged-in user's own data.
  /// Wraps API call to `GET /data`.
  Future<User> getUser() async {
    final data = await _apiService.get('/user');
    return User.fromJson(data);
  }

  /// Updates the logged-in user's entire data.
  /// Wraps API call to `PUT /user`.
  /// Returns the updated user.
  Future<User> updateUser(User user) async {
    await _apiService.put('/user', body: user.toJson());
    // Return the user we just sent, assuming success
    return user;
  }

  /// Adds a single competence tag to the user.
  /// Wraps API call to `POST /user/competencies`.
  /// Returns the updated user.
  Future<User> addCompetence(String competence) async {
    // Create competence object with title field (other fields can be added later)
    final competenceObj = {
      'title': competence,
      'description': '',
      'category': '',
      'price_range': '',
    };
    final data = await _apiService.post('/user/competencies', body: {'competence': competenceObj});
    // API returns the updated user object
    return User.fromJson(data);
  }

  /// Removes a single competence tag from the user.
  /// Wraps API call to `DELETE /user/competencies/{competence_id}`.
  /// Returns the updated user.
  Future<User> removeCompetence(String competenceId) async {
    final data = await _apiService.delete('/user/competencies/${Uri.encodeComponent(competenceId)}');
    // API returns the updated user object
    return User.fromJson(data);
  }

  /// Fetches proper public data for another user (e.g. a request sender).
  /// Wraps API call to `GET /users/{id}/user`.
  Future<User?> getOtherUser(String userId) async {
    final data = await _apiService.get('/users/${Uri.encodeComponent(userId)}/user');
    if (data != null) {
      return User.fromJson(data);
    }
    return null;
  }

  /// Adds a new service request.
  /// Wraps API call to `POST /service_requests`.
  Future<void> addServiceRequest(ServiceRequest request) async {
    await _apiService.post('/service_requests', body: request.toJson());
  }

  /// Updates the status (Accepted, Rejected, Completed) of an existing service request.
  /// Wraps API call to `PUT /service_requests/{requestId}/status`.
  Future<void> updateServiceRequestStatus(String requestId, RequestStatus status) async {
    await _apiService.put('/service_requests/${Uri.encodeComponent(requestId)}/status', body: {'status': status.name});
  }
}
