import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/theme/app_theme_colors.dart';
import '../../../../core/widgets/app_background.dart';

/// Opens a legal document hosted on GitHub Pages in the system's in-app browser
/// (Chrome Custom Tab on Android, SFSafariViewController on iOS).
class LegalPage extends StatelessWidget {
  final String title;
  final String url;

  const LegalPage({
    super.key,
    required this.title,
    required this.url,
  });

  Future<void> _launch(BuildContext context) async {
    final uri = Uri.parse(url);
    final launched = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
    if (!context.mounted) return;
    if (!launched) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open the document.')),
      );
    }
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    // Immediately trigger the in-app browser and show a minimal loading screen
    // while the browser opens.
    WidgetsBinding.instance.addPostFrameCallback((_) => _launch(context));

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
          const Center(child: CircularProgressIndicator()),
        ],
      ),
    );
  }
}
