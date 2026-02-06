import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/presentation/viewmodels/home_tab_view_model.dart';
import 'package:connectx/models/service_request.dart';
import 'package:connectx/models/user.dart';
import 'package:connectx/models/service_category.dart';
import '../../../../helpers/test_helpers.mocks.dart';

void main() {
  late HomeTabViewModel viewModel;
  late MockHomeRepository mockRepository;

  setUp(() {
    mockRepository = MockHomeRepository();
    viewModel = HomeTabViewModel(repository: mockRepository);
  });

  group('loadData', () {
    test('loads requests, favorites and user', () async {
      // Arrange
      final mockRequests = <ServiceRequest>[];
      final mockFavorites = <User>[];
      final mockUser = User(
          userId: 'user_1',
          name: 'Me',
          introduction: 'Hi',
          competencies: [],
          averageRating: 0,
          reviewCount: 0,
          positiveFeedback: [],
          negativeFeedback: []
      );

      when(mockRepository.getRequests()).thenAnswer((_) async => mockRequests);
      when(mockRepository.getFavorites()).thenAnswer((_) async => mockFavorites);
      when(mockRepository.getUser()).thenAnswer((_) async => mockUser);

      // Act
      await viewModel.loadData();

      // Assert
      expect(viewModel.isLoading, false);
      expect(viewModel.incomingRequests, isEmpty);
      expect(viewModel.outgoingRequests, isEmpty);
      expect(viewModel.favorites, isEmpty);
      expect(viewModel.user, mockUser);
      
      verify(mockRepository.getRequests()).called(1);
      verify(mockRepository.getFavorites()).called(1);
      verify(mockRepository.getUser()).called(1);
    });

    test('filters requests into incoming and outgoing', () async {
      // Arrange
      final req1 = ServiceRequest(
          service_request_id: '1', title: 'In', amountValue: 10, startDate: DateTime(2023),
          userName: 'U', userInitials: 'I', category: ServiceCategory.housekeeping,
          type: RequestType.incoming, status: RequestStatus.pending, description: '', location: ''
      );
      final req2 = ServiceRequest(
          service_request_id: '2', title: 'Out', amountValue: 10, startDate: DateTime(2023),
          userName: 'U', userInitials: 'I', category: ServiceCategory.housekeeping,
          type: RequestType.outgoing, status: RequestStatus.pending, description: '', location: ''
      );
      
      final mockUser = User(
          userId: 'user_1', name: 'Me', introduction: 'Hi', competencies: [], averageRating: 0,
          reviewCount: 0, positiveFeedback: [], negativeFeedback: []
      );
      
      when(mockRepository.getRequests()).thenAnswer((_) async => [req1, req2]);
      when(mockRepository.getFavorites()).thenAnswer((_) async => []);
      when(mockRepository.getUser()).thenAnswer((_) async => mockUser);

      // Act
      await viewModel.loadData();

      // Assert
      expect(viewModel.incomingRequests.length, 1);
      expect(viewModel.incomingRequests.first, req1);
      expect(viewModel.outgoingRequests.length, 1);
      expect(viewModel.outgoingRequests.first, req2);
    });
  });
}
