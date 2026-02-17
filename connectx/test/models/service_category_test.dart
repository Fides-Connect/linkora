import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/models/service_category.dart';

void main() {
  group('ServiceCategoryExtension', () {
    test('fromJson parses exact matches', () {
      expect(ServiceCategoryExtension.fromJson('pets'), ServiceCategory.pets);
      expect(ServiceCategoryExtension.fromJson('technology'), ServiceCategory.technology);
      expect(ServiceCategoryExtension.fromJson('electrical'), ServiceCategory.electrical);
    });

    test('fromJson parses mixed-case matches', () {
      expect(ServiceCategoryExtension.fromJson('Pets'), ServiceCategory.pets);
      expect(ServiceCategoryExtension.fromJson('TECHNOLOGY'), ServiceCategory.technology);
      expect(ServiceCategoryExtension.fromJson('Electrical'), ServiceCategory.electrical);
      expect(ServiceCategoryExtension.fromJson('GaRdEnInG'), ServiceCategory.gardening);
    });

    test('fromJson falls back to other for unknown strings', () {
      expect(ServiceCategoryExtension.fromJson('unknown_category'), ServiceCategory.other);
      expect(ServiceCategoryExtension.fromJson(''), ServiceCategory.other);
    });

    test('icon mapping is correct for electrical', () {
      expect(ServiceCategory.electrical.icon, Icons.bolt);
      expect(ServiceCategory.plumbing.icon, Icons.plumbing);
      expect(ServiceCategory.teaching.icon, Icons.school);
    });
    
    test('toJson returns name', () {
      expect(ServiceCategory.electrical.toJson(), 'electrical');
      expect(ServiceCategory.technology.toJson(), 'technology');
      expect(ServiceCategory.childcare.toJson(), 'childcare');
    });
  });
}
