import 'dart:async';
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
    // Provide a default stub so that _startWatchingRequests() (called after
    // loadData fetches the user) does not throw on unstubbed calls.
    when(mockRepository.watchServiceRequests(any))
        .thenAnswer((_) => const Stream.empty());
    viewModel = HomeTabViewModel(repository: mockRepository);
  });

  tearDown(() => viewModel.dispose());

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

  group('real-time updates', () {
    test('reloads requests when Firestore emits a change', () async {
      // Arrange
      final streamController = StreamController<void>();
      when(mockRepository.watchServiceRequests(any))
          .thenAnswer((_) => streamController.stream);

      final mockUser = User(
        id: 'user_1',
        name: 'Me',
        selfIntroduction: 'Hi',
        competencies: [],
        averageRating: 0,
        reviewCount: 0,
        feedbackPositive: [],
        feedbackNegative: [],
      );
      final newRequest = ServiceRequest(
        serviceRequestId: 'new_1',
        title: 'New Incoming',
        amountValue: 50,
        startDate: DateTime(2026),
        seekerUserId: 'other_user',
        seekerUserName: 'Other',
        seekerUserInitials: 'OU',
        selectedProviderUserId: 'user_1',
        selectedProviderUserName: 'Me',
        selectedProviderUserInitials: 'ME',
        category: ServiceCategory.housekeeping,
        status: RequestStatus.pending,
        description: '',
        location: '',
      );

      when(mockRepository.getUser()).thenAnswer((_) async => mockUser);
      when(mockRepository.getFavorites()).thenAnswer((_) async => []);
      // First call (from loadData) returns empty; second call (from _reloadRequests)
      // returns the new request.
      var callCount = 0;
      when(mockRepository.getRequests()).thenAnswer((_) async {
        callCount++;
        return callCount == 1 ? [] : [newRequest];
      });

      // Act – initial load
      await viewModel.loadData();
      expect(viewModel.incomingRequests, isEmpty);

      // Act – simulate a Firestore change event
      streamController.add(null);
      await Future<void>.delayed(Duration.zero); // allow microtask queue to flush

      // Assert – UI reflects the new request
      expect(viewModel.incomingRequests.length, 1);
      expect(viewModel.incomingRequests.first.serviceRequestId, 'new_1');
      expect(callCount, 2);

      await streamController.close();
    });
  });
}
