class FavoriteProfile {
  final String name;
  final String introduction;
  final List<String> competencies;
  final double rating;
  final int reviewCount;
  final List<String> positiveFeedback;
  final List<String> negativeFeedback;

  const FavoriteProfile({
    required this.name,
    required this.introduction,
    required this.competencies,
    required this.rating,
    required this.reviewCount,
    required this.positiveFeedback,
    required this.negativeFeedback,
  });
}

final List<FavoriteProfile> mockFavorites = [
  FavoriteProfile(
    name: "Sarah Miller",
    introduction: "I love helping seniors with their daily grocery shopping and providing company. I'm a patient listener and enjoy knitting.",
    competencies: ["Grocery Shopping", "Knitting", "Listening", "Patience"],
    rating: 4.9,
    reviewCount: 45,
    positiveFeedback: ["Very kind", "Punctual", "Great listener"],
    negativeFeedback: [],
  ),
  FavoriteProfile(
    name: "David Chen",
    introduction: "Tech enthusiast who enjoys teaching others how to use smartphones and tablets. I can also help with minor computer repairs.",
    competencies: ["Smartphone Setup", "Tablet Basics", "Computer Repair", "WiFi Troubleshooting"],
    rating: 4.7,
    reviewCount: 32,
    positiveFeedback: ["Knowledgeable", "Patient teacher"],
    negativeFeedback: ["Talks fast"],
  ),
  FavoriteProfile(
    name: "Maria Garcia",
    introduction: "Certified nurse assistant with experience in elderly care. I can help with mobility, medication reminders, and light housekeeping.",
    competencies: ["Elderly Care", "Medication Reminders", "Mobility Assistance", "Housekeeping"],
    rating: 5.0,
    reviewCount: 15,
    positiveFeedback: ["Angel", "Professional", "Caring"],
    negativeFeedback: [],
  ),
];
