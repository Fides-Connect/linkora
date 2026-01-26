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

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SupporterProfile &&
          runtimeType == other.runtimeType &&
          name == other.name;

  @override
  int get hashCode => name.hashCode;
}
