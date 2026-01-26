import 'package:flutter/material.dart';

enum RequestType { incoming, outgoing }
enum RequestStatus { pending, waitingForAnswer, completed, accepted, rejected }

class ServiceRequest {
  final String id;
  final String title;
  final String amount;
  final String date;
  final String? secondDateLine; // For "To: ..."
  final String userName;
  final String userInitials;
  final IconData icon;
  final RequestType type;
  final RequestStatus status;
  final String? updateText;
  final String description;
  final String location;

  const ServiceRequest({
    required this.id,
    required this.title,
    required this.amount,
    required this.date,
    this.secondDateLine,
    required this.userName,
    required this.userInitials,
    required this.icon,
    required this.type,
    required this.status,
    this.updateText,
    required this.description,
    required this.location,
  });
}
