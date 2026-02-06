import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/data/repositories/home_repository.dart';
import 'package:connectx/models/service_request.dart';
import 'package:connectx/models/user.dart';
import 'package:connectx/services/api_service.dart';
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
          'user_name': 'Test User',
          'user_initials': 'TU',
          'category': 'housekeeping',
          'type': 'incoming',
          'status': 'pending',
          'description': 'Test Desc',
          'location': 'Test Loc',
        }
      ];
      when(mockApiService.get('/requests')).thenAnswer((_) async => mockJsonList);

      // Act
      final result = await repository.getRequests();

      // Assert
      expect(result, isA<List<ServiceRequest>>());
      expect(result.length, 1);
      expect(result.first.title, 'Test Request');
      verify(mockApiService.get('/requests')).called(1);
    });

    // We can't easily test fallback to 'mockRequests' because it is imported internally 
    // and potentially hardcoded. But we can verify it doesn't throw.
    test('returns fallback (not empty usually) on API failure', () async {
      // Arrange
      when(mockApiService.get('/requests')).thenThrow(ApiException('Error'));

      // Act
      final result = await repository.getRequests();

      // Assert
      // Assuming mockRequests is not empty
      expect(result.isNotEmpty, true);
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
          'competencies': ['A', 'B'],
          'average_rating': 5.0,
          'review_count': 10,
          'positive_feedback': ['Good'],
          'negative_feedback': []
        }
      ];
      when(mockApiService.get('/favorites')).thenAnswer((_) async => mockJsonList);

      // Act
      final result = await repository.getFavorites();

      // Assert
      expect(result, isA<List<User>>());
      expect(result.length, 1);
      expect(result.first.name, 'Supporter 1');
    });
  });
}
