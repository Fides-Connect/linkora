import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../widgets/user_header.dart';

class HomeTabPage extends StatelessWidget {
  const HomeTabPage({super.key});

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
                'Home Screen (Empty)',
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
