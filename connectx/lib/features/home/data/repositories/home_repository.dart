import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../mock_home_data.dart';

class HomeRepository {
  // Simulate API calls with Future
  Future<List<ServiceRequest>> getRequests() async {
    // In the future, this will be: return apiService.getRequests();
    await Future.delayed(const Duration(milliseconds: 500)); // Simulate returning mock data delay
    return mockRequests;
  }

  Future<List<SupporterProfile>> getFavorites() async {
     await Future.delayed(const Duration(milliseconds: 500));
    return mockFavorites;
  }

  Future<SupporterProfile> getSupporterProfile() async {
     await Future.delayed(const Duration(milliseconds: 500));
    return mockSupporterProfile;
  }
}
