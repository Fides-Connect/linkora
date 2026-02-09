import 'package:flutter/material.dart';

enum ServiceCategory {
  pets,
  housekeeping,
  restaurant,
  technology,
  gardening,
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
      case ServiceCategory.other:
        return Icons.help_outline;
    }
  }

  String toJson() => name;

  static ServiceCategory fromJson(String json) {
    return ServiceCategory.values.firstWhere(
      (e) => e.name == json,
      orElse: () => ServiceCategory.other,
    );
  }
}
