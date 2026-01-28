import 'package:flutter/foundation.dart';

class SupporterProfile {
  final String name;
  final String introduction;
  final List<String> competencies;
  final double rating;
  final int reviewCount;
  final List<String> positiveFeedback;
  final List<String> negativeFeedback;

  const SupporterProfile({
    required this.name,
    required this.introduction,
    required this.competencies,
    required this.rating,
    required this.reviewCount,
    required this.positiveFeedback,
    required this.negativeFeedback,
  });

  factory SupporterProfile.fromJson(Map<String, dynamic> json) {
    return SupporterProfile(
      name: json['name'] as String,
      introduction: json['introduction'] as String,
      competencies: (json['competencies'] as List).cast<String>(),
      rating: (json['rating'] as num).toDouble(),
      reviewCount: json['review_count'] as int,
      positiveFeedback: (json['positive_feedback'] as List).cast<String>(),
      negativeFeedback: (json['negative_feedback'] as List).cast<String>(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'introduction': introduction,
      'competencies': competencies,
      'rating': rating,
      'review_count': reviewCount,
      'positive_feedback': positiveFeedback,
      'negative_feedback': negativeFeedback,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is SupporterProfile &&
        other.name == name &&
        other.introduction == introduction &&
        listEquals(other.competencies, competencies) &&
        other.rating == rating &&
        other.reviewCount == reviewCount &&
        listEquals(other.positiveFeedback, positiveFeedback) &&
        listEquals(other.negativeFeedback, negativeFeedback);
  }

  @override
  int get hashCode => Object.hash(
        name,
        introduction,
        Object.hashAll(competencies),
        rating,
        reviewCount,
        Object.hashAll(positiveFeedback),
        Object.hashAll(negativeFeedback),
      );
}
