import 'package:flutter/foundation.dart';
import 'competence.dart';

class User {
  final String userId;
  final String name;
  final String introduction;
  final String location;
  final String email;
  final String photoUrl;
  final bool isServiceProvider;
  final List<Competence> competencies;
  final double averageRating;
  final int reviewCount;
  final List<String> positiveFeedback;
  final List<String> negativeFeedback;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const User({
    required this.userId,
    required this.name,
    required this.introduction,
    this.location = '',
    this.email = '',
    this.photoUrl = '',
    this.isServiceProvider = false,
    required this.competencies,
    required this.averageRating,
    required this.reviewCount,
    required this.positiveFeedback,
    required this.negativeFeedback,
    this.createdAt,
    this.updatedAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id'] as String,
      name: json['name'] as String,
      introduction: json['introduction'] as String? ?? '',
      location: json['location'] as String? ?? '',
      email: json['email'] as String? ?? '',
      photoUrl: json['photo_url'] as String? ?? '',
      isServiceProvider: json['is_service_provider'] as bool? ?? false,
      competencies: (json['competencies'] as List?)
          ?.map((comp) => Competence.fromJson(comp as Map<String, dynamic>))
          .toList() ?? [],
      averageRating: (json['average_rating'] as num?)?.toDouble() ?? 0.0,
      reviewCount: json['review_count'] as int? ?? 0,
      positiveFeedback: (json['positive_feedback'] as List?)?.cast<String>() ?? [],
      negativeFeedback: (json['negative_feedback'] as List?)?.cast<String>() ?? [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'] as String) : null,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'] as String) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'name': name,
      'introduction': introduction,
      'location': location,
      'email': email,
      'photo_url': photoUrl,
      'is_service_provider': isServiceProvider,
      'competencies': competencies.map((c) => c.toJson()).toList(),
      'average_rating': averageRating,
      'review_count': reviewCount,
      'positive_feedback': positiveFeedback,
      'negative_feedback': negativeFeedback,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  User copyWith({
    String? userId,
    String? name,
    String? introduction,
    String? location,
    String? email,
    String? photoUrl,
    bool? isServiceProvider,
    List<Competence>? competencies,
    double? averageRating,
    int? reviewCount,
    List<String>? positiveFeedback,
    List<String>? negativeFeedback,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return User(
      userId: userId ?? this.userId,
      name: name ?? this.name,
      introduction: introduction ?? this.introduction,
      location: location ?? this.location,
      email: email ?? this.email,
      photoUrl: photoUrl ?? this.photoUrl,
      isServiceProvider: isServiceProvider ?? this.isServiceProvider,
      competencies: competencies != null
          ? List<Competence>.from(competencies)
          : List<Competence>.from(this.competencies),
      averageRating: averageRating ?? this.averageRating,
      reviewCount: reviewCount ?? this.reviewCount,
      positiveFeedback: positiveFeedback != null
          ? List<String>.from(positiveFeedback)
          : List<String>.from(this.positiveFeedback),
      negativeFeedback: negativeFeedback != null
          ? List<String>.from(negativeFeedback)
          : List<String>.from(this.negativeFeedback),
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is User &&
        other.userId == userId &&
        other.name == name &&
        other.introduction == introduction &&
        other.location == location &&
        other.email == email &&
        other.photoUrl == photoUrl &&
        other.isServiceProvider == isServiceProvider &&
        listEquals(other.competencies, competencies) &&
        other.averageRating == averageRating &&
        other.reviewCount == reviewCount &&
        listEquals(other.positiveFeedback, positiveFeedback) &&
        listEquals(other.negativeFeedback, negativeFeedback) &&
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt;
  }

  @override
  int get hashCode => Object.hash(
        userId,
        name,
        introduction,
        location,
        email,
        photoUrl,
        isServiceProvider,
        Object.hashAll(competencies),
        averageRating,
        reviewCount,
        Object.hashAll(positiveFeedback),
        Object.hashAll(negativeFeedback),
        createdAt,
        updatedAt,
      );
}
