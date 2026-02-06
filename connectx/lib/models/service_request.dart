import 'service_category.dart';

enum RequestType { incoming, outgoing, unknown }
enum RequestStatus { pending, waitingForAnswer, completed, accepted, rejected, unknown }

class ServiceRequest {
  final String service_request_id;
  final String title;
  final double amountValue;
  final String currency;
  final DateTime startDate;
  final DateTime? endDate;
  final String seekerUserId;
  final String seekerUserName;
  final String seekerUserInitials;
  final String providerUserId;
  final String providerUserName;
  final String providerUserInitials;
  final ServiceCategory category;
  final RequestStatus status;
  final String? updateText;
  final String description;
  final String location;

  const ServiceRequest({
    required this.service_request_id,
    required this.title,
    required this.amountValue,
    this.currency = '€',
    required this.startDate,
    this.endDate,
    required this.seekerUserId,
    required this.seekerUserName,
    required this.seekerUserInitials,
    required this.providerUserId,
    required this.providerUserName,
    required this.providerUserInitials,
    required this.category,
    required this.status,
    this.updateText,
    required this.description,
    required this.location,
  });

  factory ServiceRequest.fromJson(Map<String, dynamic> json) {
    return ServiceRequest(
      service_request_id: json['service_request_id'] as String,
      title: json['title'] as String,
      amountValue: (json['amount_value'] as num).toDouble(),
      currency: json['currency'] as String? ?? '€',
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] != null ? DateTime.parse(json['end_date'] as String) : null,
      seekerUserId: json['seeker_user_id'] as String,
      seekerUserName: json['seeker_user_name'] as String,
      seekerUserInitials: json['seeker_user_initials'] as String,
      providerUserId: json['provider_user_id'] as String,
      providerUserName: json['provider_user_name'] as String,
      providerUserInitials: json['provider_user_initials'] as String,
      category: ServiceCategoryExtension.fromJson(json['category'] as String),
      status: RequestStatus.values.asNameMap()[json['status'] as String] ??
          RequestStatus.unknown,
      updateText: json['update_text'] as String?,
      description: json['description'] as String,
      location: json['location'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'service_request_id': service_request_id,
      'title': title,
      'amount_value': amountValue,
      'currency': currency,
      'start_date': startDate.toIso8601String(),
      'end_date': endDate?.toIso8601String(),
      'seeker_user_id': seekerUserId,
      'seeker_user_name': seekerUserName,
      'seeker_user_initials': seekerUserInitials,
      'provider_user_id': providerUserId,
      'provider_user_name': providerUserName,
      'provider_user_initials': providerUserInitials,
      'category': category.toJson(),
      'status': status.name,
      'update_text': updateText,
      'description': description,
      'location': location,
    };
  }

  /// Derives the request type based on the current user ID
  RequestType getType(String currentUserId) {
    if (currentUserId == seekerUserId) {
      return RequestType.outgoing;
    } else if (currentUserId == providerUserId) {
      return RequestType.incoming;
    }
    return RequestType.unknown;
  }
}
