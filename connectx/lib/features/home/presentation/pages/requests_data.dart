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

final List<ServiceRequest> mockRequests = [
  ServiceRequest(
    id: '1',
    title: 'Teach Japanese Tea Ceremony',
    amount: '+ 159.00 €',
    date: '25. February 2026',
    userName: 'Paul Shatner',
    userInitials: 'PS',
    icon: Icons.restaurant,
    type: RequestType.incoming,
    status: RequestStatus.pending,
    description: 'I would like to learn the traditional Japanese tea ceremony. I have some basic knowledge but want to deepen my understanding and practice.',
    location: 'Berlin, Mitte',
  ),
  ServiceRequest(
    id: '2',
    title: 'Cat Sitting',
    amount: '- 59.00 €',
    date: '19. December 2025',
    userName: 'Aron Neil',
    userInitials: 'AN',
    icon: Icons.pets,
    type: RequestType.outgoing,
    status: RequestStatus.waitingForAnswer,
    updateText: '1 Update',
    description: 'Looking for someone to feed my two cats and play with them for an hour while I am away for the weekend.',
    location: 'Munich, Schwabing',
  ),
  ServiceRequest(
    id: '3',
    title: 'Housekeeping',
    amount: '- 365.12 €',
    date: 'From: 19. December 2025',
    secondDateLine: 'To:     03. January 2026',
    userName: 'Jared Dang',
    userInitials: 'JD',
    icon: Icons.home,
    type: RequestType.outgoing,
    status: RequestStatus.completed,
    description: 'General housekeeping including cleaning, laundry, and plant care during my holiday vacation.',
    location: 'Hamburg, Altona',
  ),
];
