class Competence {
  final String competenceId;
  final String title;
  final String description;
  final String category;
  final String priceRange;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Competence({
    required this.competenceId,
    required this.title,
    this.description = '',
    this.category = '',
    this.priceRange = '',
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
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt;
  }

  @override
  int get hashCode => Object.hash(competenceId, title, description, category, priceRange, createdAt, updatedAt);
}
