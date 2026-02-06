class Competence {
  final String title;
  final String description;
  final String category;
  final String priceRange;

  const Competence({
    required this.title,
    this.description = '',
    this.category = '',
    this.priceRange = '',
  });

  factory Competence.fromJson(Map<String, dynamic> json) {
    return Competence(
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      category: json['category'] as String? ?? '',
      priceRange: json['price_range'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'category': category,
      'price_range': priceRange,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Competence &&
        other.title == title &&
        other.description == description &&
        other.category == category &&
        other.priceRange == priceRange;
  }

  @override
  int get hashCode => Object.hash(title, description, category, priceRange);
}
