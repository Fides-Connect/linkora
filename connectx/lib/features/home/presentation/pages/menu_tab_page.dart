import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../widgets/user_header.dart';

class MenuTabPage extends StatelessWidget {
  const MenuTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),
            const UserHeader(),
            Center(
              child: Text(
                AppLocalizations.of(context)?.menuScreenEmpty ??
                    'Menu Screen (Empty)',
                style: const TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
