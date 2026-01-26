import 'package:flutter/material.dart';

class FavoritesTabPage extends StatelessWidget {
  const FavoritesTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Favorites')),
      body: const Center(child: Text('Favorites Screen (Empty)')),
    );
  }
}
