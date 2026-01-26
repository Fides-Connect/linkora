import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../widgets/user_header.dart';

class FavoritesTabPage extends StatelessWidget {
  const FavoritesTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            AppBackground(),
            UserHeader(),
            Center(
              child: Text(
                'Favorites Screen (Empty)',
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
