import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/data/repositories/home_repository.dart';
import 'package:connectx/models/service_request.dart';
import 'package:connectx/models/user.dart';
import '../../../../helpers/test_helpers.mocks.dart';

void main() {
  late HomeRepository repository;
  late MockApiService mockApiService;

  setUp(() {
    mockApiService = MockApiService();
    repository = HomeRepository(apiService: mockApiService);
  });

  group('getRequests', () {
    test('returns list of ServiceRequests on successful API call', () async {
      // Arrange
      final mockJsonList = [
        {
          'service_request_id': 'req_1',
          'title': 'Test Request',
          'amount_value': 100.0,
          'currency': '€',
          'start_date': '2023-01-01T00:00:00.000',
          'seeker_user_id': 'seeker_1',
          'seeker_user_name': 'Test Seeker',
          'seeker_user_initials': 'TS',
          'selected_provider_user_id': 'provider_1',
          'selected_provider_user_name': 'Test Provider',
          'selected_provider_user_initials': 'TP',
          'category': 'housekeeping',
          'status': 'pending',
          'description': 'Test Desc',
          'location': 'Test Loc',
        }
      ];
      when(mockApiService.get('/api/v1/service-requests')).thenAnswer((_) async => mockJsonList);

      // Act
      final result = await repository.getRequests();

      // Assert
      expect(result, isA<List<ServiceRequest>>());
      expect(result.length, 1);
      expect(result.first.title, 'Test Request');
      verify(mockApiService.get('/api/v1/service-requests')).called(1);
    });


  });

  group('getFavorites', () {
    test('returns list of Users on successful API call', () async {
       // Arrange
      final mockJsonList = [
        {
          'user_id': 'user_1',
          'name': 'Supporter 1',
          'introduction': 'Intro',
          'competencies': [
            {'competence_id': 'comp1', 'title': 'A', 'description': '', 'category': '', 'price_range': ''},
            {'competence_id': 'comp2', 'title': 'B', 'description': '', 'category': '', 'price_range': ''}
          ],
          'average_rating': 5.0,
          'review_count': 10,
          'positive_feedback': ['Good'],
          'negative_feedback': []
        }
      ];
      when(mockApiService.get('/api/v1/me/favorites')).thenAnswer((_) async => mockJsonList);

      // Act
      final result = await repository.getFavorites();

      // Assert
      expect(result, isA<List<User>>());
      expect(result.length, 1);
      expect(result.first.name, 'Supporter 1');
    });
  });
}
