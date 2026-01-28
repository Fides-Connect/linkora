import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/presentation/viewmodels/home_tab_view_model.dart';
import 'package:connectx/models/service_request.dart';
import 'package:connectx/models/supporter_profile.dart';
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
    test('loads requests, favorites and profile', () async {
      // Arrange
      final mockRequests = <ServiceRequest>[];
      final mockFavorites = <SupporterProfile>[];
      final mockProfile = SupporterProfile(
          name: 'Me',
          introduction: 'Hi',
          competencies: [],
          rating: 0,
          reviewCount: 0,
          positiveFeedback: [],
          negativeFeedback: []
      );

      when(mockRepository.getRequests()).thenAnswer((_) async => mockRequests);
      when(mockRepository.getFavorites()).thenAnswer((_) async => mockFavorites);
      when(mockRepository.getSupporterProfile()).thenAnswer((_) async => mockProfile);

      // Act
      await viewModel.loadData();

      // Assert
      expect(viewModel.isLoading, false);
      expect(viewModel.incomingRequests, isEmpty);
      expect(viewModel.outgoingRequests, isEmpty);
      expect(viewModel.favorites, isEmpty);
      expect(viewModel.userProfile, mockProfile);
      
      verify(mockRepository.getRequests()).called(1);
      verify(mockRepository.getFavorites()).called(1);
      verify(mockRepository.getSupporterProfile()).called(1);
    });

    test('filters requests into incoming and outgoing', () async {
      // Arrange
      final req1 = ServiceRequest(
          id: '1', title: 'In', amountValue: 10, startDate: DateTime(2023),
          userName: 'U', userInitials: 'I', category: ServiceCategory.housekeeping,
          type: RequestType.incoming, status: RequestStatus.pending, description: '', location: ''
      );
      final req2 = ServiceRequest(
          id: '2', title: 'Out', amountValue: 10, startDate: DateTime(2023),
          userName: 'U', userInitials: 'I', category: ServiceCategory.housekeeping,
          type: RequestType.outgoing, status: RequestStatus.pending, description: '', location: ''
      );
      
      final mockProfile = SupporterProfile(
          name: 'Me', introduction: 'Hi', competencies: [], rating: 0,
          reviewCount: 0, positiveFeedback: [], negativeFeedback: []
      );
      
      when(mockRepository.getRequests()).thenAnswer((_) async => [req1, req2]);
      when(mockRepository.getFavorites()).thenAnswer((_) async => []);
      when(mockRepository.getSupporterProfile()).thenAnswer((_) async => mockProfile);

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
