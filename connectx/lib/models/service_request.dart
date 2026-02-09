import 'service_category.dart';

enum RequestType { incoming, outgoing, unknown }
enum RequestStatus { pending, waitingForAnswer, completed, accepted, rejected, unknown }

class ServiceRequest {
  final String id;
  final String title;
  final double amountValue;
  final String currency;
  final DateTime startDate;
  final DateTime? endDate;
  final String userName;
  final String userInitials;
  final ServiceCategory category;
  final RequestType type;
  final RequestStatus status;
  final String? updateText;
  final String description;
  final String location;

  const ServiceRequest({
    required this.id,
    required this.title,
    required this.amountValue,
    this.currency = '€',
    required this.startDate,
    this.endDate,
    required this.userName,
    required this.userInitials,
    required this.category,
    required this.type,
    required this.status,
    this.updateText,
    required this.description,
    required this.location,
  });

  factory ServiceRequest.fromJson(Map<String, dynamic> json) {
    return ServiceRequest(
      id: json['id'] as String,
      title: json['title'] as String,
      amountValue: (json['amount_value'] as num).toDouble(),
      currency: json['currency'] as String? ?? '€',
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] != null ? DateTime.parse(json['end_date'] as String) : null,
      userName: json['user_name'] as String,
      userInitials: json['user_initials'] as String,
      category: ServiceCategoryExtension.fromJson(json['category'] as String),
      type: RequestType.values.asNameMap()[json['type'] as String] ??
          RequestType.unknown,
      status: RequestStatus.values.asNameMap()[json['status'] as String] ??
          RequestStatus.unknown,
      updateText: json['update_text'] as String?,
      description: json['description'] as String,
      location: json['location'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'amount_value': amountValue,
      'currency': currency,
      'start_date': startDate.toIso8601String(),
      'end_date': endDate?.toIso8601String(),
      'user_name': userName,
      'user_initials': userInitials,
      'category': category.toJson(),
      'type': type.name,
      'status': status.name,
      'update_text': updateText,
      'description': description,
      'location': location,
    };
  }
}
