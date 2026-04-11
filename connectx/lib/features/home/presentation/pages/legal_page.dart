import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme_colors.dart';
import '../../../../core/widgets/app_background.dart';

/// Generic legal/informational page.
///
/// To add or replace content, edit the corresponding `*Title` / `*Content`
/// constants in [MessagesEN] and [MessagesDE].
class LegalPage extends StatelessWidget {
  final String title;
  final String content;

  const LegalPage({
    super.key,
    required this.title,
    required this.content,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text(title),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: context.appPrimaryColor,
      ),
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Text(
                content,
                style: TextStyle(
                  color: context.appPrimaryColor,
                  fontSize: 14,
                  height: 1.7,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
