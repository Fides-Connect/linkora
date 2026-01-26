import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';

class FavoritesTabPage extends StatelessWidget {
  const FavoritesTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),
            Center(
              child: Text(
                AppLocalizations.of(context)?.favoritesScreenEmpty ??
                    'Favorites Screen (Empty)',
                style: const TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
