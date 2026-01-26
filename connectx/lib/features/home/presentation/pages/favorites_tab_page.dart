import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import 'profile_detail_page.dart';

class FavoritesTabPage extends StatelessWidget {
  const FavoritesTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),
            mockFavorites.isEmpty
                ? Center(
                    child: Text(
                      AppLocalizations.of(context)?.favoritesScreenEmpty ??
                          'Favorites Screen (Empty)',
                      style: const TextStyle(color: Colors.white),
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: mockFavorites.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 16),
                    itemBuilder: (context, index) {
                      final profile = mockFavorites[index];
                      return _buildFavoriteCard(context, profile);
                    },
                  ),
          ],
        ),
      ),
    );
  }

  Widget _buildFavoriteCard(BuildContext context, FavoriteProfile profile) {
    return Card(
      color: Colors.white.withOpacity(0.1),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => ProfileDetailPage(profile: profile),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 30,
                backgroundColor: Colors.white.withOpacity(0.2),
                child: Text(
                  profile.name[0],
                  style: const TextStyle(
                    fontSize: 24,
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      profile.name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      profile.introduction,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.9),
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: profile.competencies.take(3).map((comp) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            comp,
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 11,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

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

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FavoriteProfile &&
          runtimeType == other.runtimeType &&
          name == other.name;

  @override
  int get hashCode => name.hashCode;
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
