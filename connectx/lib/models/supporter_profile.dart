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
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SupporterProfile &&
          runtimeType == other.runtimeType &&
          name == other.name;

  @override
  int get hashCode => name.hashCode;
}
