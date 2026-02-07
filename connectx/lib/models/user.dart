import 'package:flutter/foundation.dart';
import 'competence.dart';

class User {
  final String userId;
  final String name;
  final String introduction;
  final List<Competence> competencies;
  final double averageRating;
  final int reviewCount;
  final List<String> positiveFeedback;
  final List<String> negativeFeedback;

  const User({
    required this.userId,
    required this.name,
    required this.introduction,
    required this.competencies,
    required this.averageRating,
    required this.reviewCount,
    required this.positiveFeedback,
    required this.negativeFeedback,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id'] as String,
      name: json['name'] as String,
      introduction: json['introduction'] as String,
      competencies: (json['competencies'] as List?)
          ?.map((comp) => Competence.fromJson(comp as Map<String, dynamic>))
          .toList() ?? [],
      averageRating: (json['average_rating'] as num).toDouble(),
      reviewCount: json['review_count'] as int,
      positiveFeedback: (json['positive_feedback'] as List?)?.cast<String>() ?? [],
      negativeFeedback: (json['negative_feedback'] as List?)?.cast<String>() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'name': name,
      'introduction': introduction,
      'competencies': competencies.map((c) => c.toJson()).toList(),
      'average_rating': averageRating,
      'review_count': reviewCount,
      'positive_feedback': positiveFeedback,
      'negative_feedback': negativeFeedback,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is User &&
        other.userId == userId &&
        other.name == name &&
        other.introduction == introduction &&
        listEquals(other.competencies, competencies) &&
        other.averageRating == averageRating &&
        other.reviewCount == reviewCount &&
        listEquals(other.positiveFeedback, positiveFeedback) &&
        listEquals(other.negativeFeedback, negativeFeedback);
  }

  @override
  int get hashCode => Object.hash(
        userId,
        name,
        introduction,
        Object.hashAll(competencies),
        averageRating,
        reviewCount,
        Object.hashAll(positiveFeedback),
        Object.hashAll(negativeFeedback),
      );
}
