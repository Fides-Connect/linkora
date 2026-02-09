class Competence {
  final String competenceId;
  final String title;
  final String description;
  final String category;
  final String priceRange;
  final int yearOfExperience;
  final List<String> feedbackPositive;
  final List<String> feedbackNegative;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Competence({
    required this.competenceId,
    required this.title,
    this.description = '',
    this.category = '',
    this.priceRange = '',
    this.yearOfExperience = 0,
    this.feedbackPositive = const [],
    this.feedbackNegative = const [],
    this.createdAt,
    this.updatedAt,
  });

  factory Competence.fromJson(Map<String, dynamic> json) {
    return Competence(
      competenceId: json['competence_id'] as String,
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      category: json['category'] as String? ?? '',
      priceRange: json['price_range'] as String? ?? '',
      yearOfExperience: json['year_of_experience'] as int? ?? 0,
      feedbackPositive: (json['feedback_positive'] as List?)?.cast<String>() ?? [],
      feedbackNegative: (json['feedback_negative'] as List?)?.cast<String>() ?? [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'] as String) : null,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'] as String) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'competence_id': competenceId,
      'title': title,
      'description': description,
      'category': category,
      'price_range': priceRange,
      'year_of_experience': yearOfExperience,
      'feedback_positive': feedbackPositive,
      'feedback_negative': feedbackNegative,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Competence &&
        other.competenceId == competenceId &&
        other.title == title &&
        other.description == description &&
        other.category == category &&
        other.priceRange == priceRange &&
        other.yearOfExperience == yearOfExperience &&
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt;
  }

  @override
  int get hashCode => Object.hash(competenceId, title, description, category, priceRange, yearOfExperience, createdAt, updatedAt);
}
