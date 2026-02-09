import 'package:flutter/foundation.dart';
import 'competence.dart';

class User {
  final String userId;
  final String name;
  final String selfIntroduction;
  final String location;
  final String email;
  final String photoUrl;
  final bool isServiceProvider;
  final List<Competence> competencies;
  final double averageRating;
  final int reviewCount;
  final List<String> feedbackPositive;
  final List<String> feedbackNegative;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const User({
    required this.userId,
    required this.name,
    required this.selfIntroduction,
    this.location = '',
    this.email = '',
    this.photoUrl = '',
    this.isServiceProvider = false,
    required this.competencies,
    required this.averageRating,
    required this.reviewCount,
    required this.feedbackPositive,
    required this.feedbackNegative,
    this.createdAt,
    this.updatedAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id'] as String,
      name: json['name'] as String,
      selfIntroduction: json['self_introduction'] as String? ?? '',
      location: json['location'] as String? ?? '',
      email: json['email'] as String? ?? '',
      photoUrl: json['photo_url'] as String? ?? '',
      isServiceProvider: json['is_service_provider'] as bool? ?? false,
      competencies: (json['competencies'] as List?)
          ?.map((comp) => Competence.fromJson(comp as Map<String, dynamic>))
          .toList() ?? [],
      averageRating: (json['average_rating'] as num?)?.toDouble() ?? 0.0,
      reviewCount: json['review_count'] as int? ?? 0,
      feedbackPositive: (json['feedback_positive'] as List?)?.cast<String>() ?? [],
      feedbackNegative: (json['feedback_negative'] as List?)?.cast<String>() ?? [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'] as String) : null,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'] as String) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'name': name,
      'self_introduction': selfIntroduction,
      'location': location,
      'email': email,
      'photo_url': photoUrl,
      'is_service_provider': isServiceProvider,
      'competencies': competencies.map((c) => c.toJson()).toList(),
      'average_rating': averageRating,
      'review_count': reviewCount,
      'feedback_positive': feedbackPositive,
      'feedback_negative': feedbackNegative,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  User copyWith({
    String? userId,
    String? name,
    String? selfIntroduction,
    String? location,
    String? email,
    String? photoUrl,
    bool? isServiceProvider,
    List<Competence>? competencies,
    double? averageRating,
    int? reviewCount,
    List<String>? feedbackPositive,
    List<String>? feedbackNegative,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return User(
      userId: userId ?? this.userId,
      name: name ?? this.name,
      selfIntroduction: selfIntroduction ?? this.selfIntroduction,
      location: location ?? this.location,
      email: email ?? this.email,
      photoUrl: photoUrl ?? this.photoUrl,
      isServiceProvider: isServiceProvider ?? this.isServiceProvider,
      competencies: competencies != null
          ? List<Competence>.from(competencies)
          : List<Competence>.from(this.competencies),
      averageRating: averageRating ?? this.averageRating,
      reviewCount: reviewCount ?? this.reviewCount,
      feedbackPositive: feedbackPositive != null
          ? List<String>.from(feedbackPositive)
          : List<String>.from(this.feedbackPositive),
      feedbackNegative: feedbackNegative != null
          ? List<String>.from(feedbackNegative)
          : List<String>.from(this.feedbackNegative),
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
        other.selfIntroduction == selfIntroduction &&
        other.location == location &&
        other.email == email &&
        other.photoUrl == photoUrl &&
        other.isServiceProvider == isServiceProvider &&
        listEquals(other.competencies, competencies) &&
        other.averageRating == averageRating &&
        other.reviewCount == reviewCount &&
        listEquals(other.feedbackPositive, feedbackPositive) &&
        listEquals(other.feedbackNegative, feedbackNegative) &&
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt;
  }

  @override
  int get hashCode => Object.hash(
        userId,
        name,
        selfIntroduction,
        location,
        email,
        photoUrl,
        isServiceProvider,
        Object.hashAll(competencies),
        averageRating,
        reviewCount,
        Object.hashAll(feedbackPositive),
        Object.hashAll(feedbackNegative),
        createdAt,
        updatedAt,
      );
}
