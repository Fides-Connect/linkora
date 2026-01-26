import 'package:flutter/foundation.dart';
import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../../data/repositories/home_repository.dart';

class HomeTabViewModel extends ChangeNotifier {
  final HomeRepository _repository;
  
  List<ServiceRequest> _incomingRequests = [];
  List<ServiceRequest> _outgoingRequests = [];
  List<SupporterProfile> _favorites = [];
  SupporterProfile? _userProfile;
  
  bool _isLoading = false;
  String? _error;

  HomeTabViewModel({HomeRepository? repository}) 
      : _repository = repository ?? HomeRepository();

  List<ServiceRequest> get incomingRequests => _incomingRequests;
  List<ServiceRequest> get outgoingRequests => _outgoingRequests;
  List<SupporterProfile> get favorites => _favorites;
  SupporterProfile? get userProfile => _userProfile;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadData() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final requests = await _repository.getRequests();
      _incomingRequests = requests.where((r) => r.type == RequestType.incoming).toList();
      _outgoingRequests = requests.where((r) => r.type == RequestType.outgoing).toList();
      
      _favorites = await _repository.getFavorites();
      _userProfile = await _repository.getSupporterProfile();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
