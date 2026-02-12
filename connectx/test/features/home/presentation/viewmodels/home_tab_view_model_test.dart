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
          id: 'user_1',
          name: 'Me',
          selfIntroduction: 'Hi',
          competencies: [],
          averageRating: 0,
          reviewCount: 0,
          feedbackPositive: [],
          feedbackNegative: []
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
      final mockUser = User(
          id: 'user_1', name: 'Me', selfIntroduction: 'Hi', competencies: [], averageRating: 0,
          reviewCount: 0, feedbackPositive: [], feedbackNegative: []
      );
      
      final req1 = ServiceRequest(
          serviceRequestId: '1', title: 'In', amountValue: 10, startDate: DateTime(2023),
          seekerUserId: 'other_user', seekerUserName: 'Other', seekerUserInitials: 'OU',
          selectedProviderUserId: 'user_1', selectedProviderUserName: 'Me', selectedProviderUserInitials: 'ME',
          category: ServiceCategory.housekeeping,
          status: RequestStatus.pending, description: '', location: ''
      );
      final req2 = ServiceRequest(
          serviceRequestId: '2', title: 'Out', amountValue: 10, startDate: DateTime(2023),
          seekerUserId: 'user_1', seekerUserName: 'Me', seekerUserInitials: 'ME',
          selectedProviderUserId: 'other_user', selectedProviderUserName: 'Other', selectedProviderUserInitials: 'OU',
          category: ServiceCategory.housekeeping,
          status: RequestStatus.pending, description: '', location: ''
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
