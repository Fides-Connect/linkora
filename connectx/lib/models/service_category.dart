import 'package:flutter/material.dart';

enum ServiceCategory {
  pets,
  housekeeping,
  restaurant,
  technology,
  gardening,
  electrical,
  plumbing,
  repair,
  teaching,
  transport,
  childcare,
  wellness,
  events,
  other,
}

extension ServiceCategoryExtension on ServiceCategory {
  IconData get icon {
    switch (this) {
      case ServiceCategory.pets:
        return Icons.pets;
      case ServiceCategory.housekeeping:
        return Icons.home;
      case ServiceCategory.restaurant:
        return Icons.restaurant;
      case ServiceCategory.technology:
        return Icons.computer;
      case ServiceCategory.gardening:
        return Icons.yard;
      case ServiceCategory.electrical:
        return Icons.bolt;
      case ServiceCategory.plumbing:
        return Icons.plumbing;
      case ServiceCategory.repair:
        return Icons.build;
      case ServiceCategory.teaching:
        return Icons.school;
      case ServiceCategory.transport:
        return Icons.directions_car;
      case ServiceCategory.childcare:
        return Icons.child_care;
      case ServiceCategory.wellness:
        return Icons.spa;
      case ServiceCategory.events:
        return Icons.event;
      case ServiceCategory.other:
        return Icons.help_outline;
    }
  }

  String toJson() => name;

  static ServiceCategory fromJson(String json) {
    return ServiceCategory.values.firstWhere(
      (e) => e.name.toLowerCase() == json.toLowerCase(),
      orElse: () => ServiceCategory.other,
    );
  }
}
