/// Data model for a provider card received from the backend.
class ProviderCardData {
  final String name;
  final String description;
  final String reasoning;
  final double? rating;
  final int? ratingCount;
  final String? website;
  final String? phone;
  final String? address;
  final String? photoUrl;
  final String? openingHours;
  final String? mapsUrl;
  final String? email;
  final String emailSubject;
  final String emailBody;
  final String language;
  final String source;

  const ProviderCardData({
    required this.name,
    required this.description,
    required this.reasoning,
    this.rating,
    this.ratingCount,
    this.website,
    this.phone,
    this.address,
    this.photoUrl,
    this.openingHours,
    this.mapsUrl,
    this.email,
    this.emailSubject = '',
    this.emailBody = '',
    this.language = 'en',
    this.source = 'google_places',
  });

  factory ProviderCardData.fromJson(Map<String, dynamic> json) {
    return ProviderCardData(
      name: (json['name'] as String?) ?? '',
      description: (json['description'] as String?) ?? '',
      reasoning: (json['reasoning'] as String?) ?? '',
      rating: (json['rating'] as num?)?.toDouble(),
      ratingCount: (json['rating_count'] as num?)?.toInt(),
      website: json['website'] as String?,
      phone: json['phone'] as String?,
      address: json['address'] as String?,
      photoUrl: json['photo_url'] as String?,
      openingHours: json['opening_hours'] as String?,
      mapsUrl: json['maps_url'] as String?,
      email: json['email'] as String?,
      emailSubject: (json['email_subject'] as String?) ?? '',
      emailBody: (json['email_body'] as String?) ?? '',
      language: (json['language'] as String?) ?? 'en',
      source: (json['source'] as String?) ?? 'google_places',
    );
  }
}
