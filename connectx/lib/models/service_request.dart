import 'service_category.dart';

enum RequestType { incoming, outgoing, unknown }

enum RequestStatus {
  pending,
  accepted,
  rejected,
  active,
  waitingForAnswer,
  completed,
  serviceProvided,
  cancelled,
  expired,
  unknown,
}

class ServiceRequest {
  final String serviceRequestId;
  final String title;
  final double amountValue;
  final String currency;
  final DateTime startDate;
  final DateTime? endDate;
  final String seekerUserId;
  final String seekerUserName;
  final String seekerUserInitials;
  final String selectedProviderUserId;
  final String selectedProviderUserName;
  final String selectedProviderUserInitials;
  final ServiceCategory category;
  final RequestStatus status;
  final String? updateText;
  final String description;
  final String location;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const ServiceRequest({
    required this.serviceRequestId,
    required this.title,
    required this.amountValue,
    this.currency = '€',
    required this.startDate,
    this.endDate,
    required this.seekerUserId,
    required this.seekerUserName,
    required this.seekerUserInitials,
    required this.selectedProviderUserId,
    required this.selectedProviderUserName,
    required this.selectedProviderUserInitials,
    required this.category,
    required this.status,
    this.updateText,
    required this.description,
    required this.location,
    this.createdAt,
    this.updatedAt,
  });

  factory ServiceRequest.fromJson(Map<String, dynamic> json) {
    return ServiceRequest(
      serviceRequestId: json['service_request_id'] as String,
      title: json['title'] as String,
      amountValue: (json['amount_value'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? '€',
      startDate: json['start_date'] != null
          ? DateTime.parse(json['start_date'] as String)
          : DateTime.now(),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'] as String)
          : null,
      seekerUserId: json['seeker_user_id'] as String,
      seekerUserName: json['seeker_user_name'] as String,
      seekerUserInitials: json['seeker_user_initials'] as String,
      selectedProviderUserId: json['selected_provider_user_id'] as String,
      selectedProviderUserName: json['selected_provider_user_name'] as String,
      selectedProviderUserInitials:
          json['selected_provider_user_initials'] as String,
      category: ServiceCategoryExtension.fromJson(json['category'] as String),
      status:
          RequestStatus.values.asNameMap()[json['status'] as String] ??
          RequestStatus.unknown,
      updateText: json['update_text'] as String?,
      description: json['description'] as String,
      location: json['location'] as String,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'service_request_id': serviceRequestId,
      'title': title,
      'amount_value': amountValue,
      'currency': currency,
      'start_date': startDate.toIso8601String(),
      'end_date': endDate?.toIso8601String(),
      'seeker_user_id': seekerUserId,
      'seeker_user_name': seekerUserName,
      'seeker_user_initials': seekerUserInitials,
      'selected_provider_user_id': selectedProviderUserId,
      'selected_provider_user_name': selectedProviderUserName,
      'selected_provider_user_initials': selectedProviderUserInitials,
      'category': category.toJson(),
      'status': status.name,
      'update_text': updateText,
      'description': description,
      'location': location,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  /// Derives the request type based on the current user ID
  RequestType getType(String currentUserId) {
    if (currentUserId == seekerUserId) {
      return RequestType.outgoing;
    } else if (currentUserId == selectedProviderUserId) {
      return RequestType.incoming;
    }
    return RequestType.unknown;
  }
}
