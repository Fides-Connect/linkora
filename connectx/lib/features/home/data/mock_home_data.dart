import 'package:flutter/material.dart';
import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';

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

final List<SupporterProfile> mockFavorites = [
  SupporterProfile(
    name: "Sarah Miller",
    introduction: "I love helping seniors with their daily grocery shopping and providing company. I'm a patient listener and enjoy knitting.",
    competencies: ["Grocery Shopping", "Knitting", "Listening", "Patience"],
    rating: 4.9,
    reviewCount: 45,
    positiveFeedback: ["Very kind", "Punctual", "Great listener"],
    negativeFeedback: [],
  ),
  SupporterProfile(
    name: "David Chen",
    introduction: "Tech enthusiast who enjoys teaching others how to use smartphones and tablets. I can also help with minor computer repairs.",
    competencies: ["Smartphone Setup", "Tablet Basics", "Computer Repair", "WiFi Troubleshooting"],
    rating: 4.7,
    reviewCount: 32,
    positiveFeedback: ["Knowledgeable", "Patient teacher"],
    negativeFeedback: ["Talks fast"],
  ),
  SupporterProfile(
    name: "Maria Garcia",
    introduction: "Certified nurse assistant with experience in elderly care. I can help with mobility, medication reminders, and light housekeeping.",
    competencies: ["Elderly Care", "Medication Reminders", "Mobility Assistance", "Housekeeping"],
    rating: 5.0,
    reviewCount: 15,
    positiveFeedback: ["Angel", "Professional", "Caring"],
    negativeFeedback: [],
  ),
];

final SupporterProfile mockSupporterProfile = SupporterProfile(
  name: "Thomas",
  introduction: "Hello, I'm Thomas! I have a deep passion for Japanese culture and helpful technology. In my free time, you can find me tending to my garden, fixing smaller things around the house, or relaxing with my cats.",
  competencies: [
    'Japanese Culture',
    'Computer',
    'Cats',
    'Home Repair',
    'Gardening',
  ],
  rating: 4.8,
  reviewCount: 124,
  positiveFeedback: ['Friendly', 'Patient', 'Knowledgeable', 'Good Communicator'],
  negativeFeedback: ['Too late'],
);
