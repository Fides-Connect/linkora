import '../../../../models/service_request.dart';
import '../../../../models/supporter_profile.dart';
import '../../../../models/service_category.dart';

// Mutable lists to allow runtime updates during mock session
List<ServiceRequest> mockRequests = [
  ServiceRequest(
    id: '1',
    title: 'Teach Japanese Tea Ceremony',
    amountValue: 159.00,
    startDate: DateTime(2026, 2, 25),
    userName: 'Paul Shatner',
    userInitials: 'PS',
    category: ServiceCategory.restaurant,
    type: RequestType.incoming,
    status: RequestStatus.pending,
    description: 'I would like to learn the traditional Japanese tea ceremony. I have some basic knowledge but want to deepen my understanding and practice.',
    location: 'Berlin, Mitte',
  ),
  ServiceRequest(
    id: '2',
    title: 'Cat Sitting',
    amountValue: 59.00,
    startDate: DateTime(2025, 12, 19),
    userName: 'Aron Neil',
    userInitials: 'AN',
    category: ServiceCategory.pets,
    type: RequestType.outgoing,
    status: RequestStatus.waitingForAnswer,
    updateText: '1 Update',
    description: 'Looking for someone to feed my two cats and play with them for an hour while I am away for the weekend.',
    location: 'Munich, Schwabing',
  ),
  ServiceRequest(
    id: '3',
    title: 'Housekeeping',
    amountValue: 365.12,
    startDate: DateTime(2025, 12, 19),
    endDate: DateTime(2026, 1, 3),
    userName: 'Jared Dang',
    userInitials: 'JD',
    category: ServiceCategory.housekeeping,
    type: RequestType.outgoing,
    status: RequestStatus.completed,
    description: 'General housekeeping including cleaning, laundry, and plant care during my holiday vacation.',
    location: 'Hamburg, Altona',
  ),
];

List<SupporterProfile> mockFavorites = [
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

// Mutable to allow updates
SupporterProfile mockSupporterProfile = SupporterProfile(
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

final Map<String, SupporterProfile> mockUserProfiles = {
  'Paul Shatner': const SupporterProfile(
    name: 'Paul Shatner',
    introduction:
        "I am fascinated by Japanese culture and have always wanted to learn the authentic tea ceremony. I am respectful and eager to learn.",
    competencies: ["Japanese Culture Enthusiast", "Tea Lover", "Student"],
    rating: 5.0,
    reviewCount: 3,
    positiveFeedback: ["Very polite", "Eager learner"],
    negativeFeedback: [],
  ),
  'Aron Neil': const SupporterProfile(
    name: 'Aron Neil',
    introduction:
        "I own two lovely cats and often need reliable sitters when I travel for work. I value communication and reliability.",
    competencies: ["Cat Owner", "Business Traveller", "Responsive"],
    rating: 4.8,
    reviewCount: 12,
    positiveFeedback: ["Clear instructions", "Friendly"],
    negativeFeedback: [],
  ),
  'Jared Dang': const SupporterProfile(
    name: 'Jared Dang',
    introduction:
        "I travel often and need help keeping my home in order. I appreciate attention to detail.",
    competencies: ["Home Owner", "Frequent Traveler"],
    rating: 4.9,
    reviewCount: 28,
    positiveFeedback: ["Generous", "Fair"],
    negativeFeedback: [],
  ),
};
