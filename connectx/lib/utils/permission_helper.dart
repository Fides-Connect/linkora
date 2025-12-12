import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../localization/app_localizations.dart';

class PermissionHelper {
  static Future<void> requestMicrophonePermission(BuildContext context) async {
    if (kIsWeb) return;

    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;

    var micStatus = await Permission.microphone.status;

    if (!micStatus.isGranted) {
      micStatus = await Permission.microphone.request();

      if (!micStatus.isGranted && context.mounted) {
        await _showDialog(
          context,
          localizations.microphonePermissionTitle,
          localizations.microphonePermissionMessage,
          localizations.okButton,
        );

        micStatus = await Permission.microphone.request();

        if (!micStatus.isGranted && context.mounted) {
          _showDialog(
            context,
            localizations.microphoneAccessDeniedTitle,
            localizations.microphoneAccessDeniedMessage,
            localizations.okButton,
          );
        }
      }
    }
  }

  static Future<void> requestNotificationPermission(BuildContext context) async {
    if (kIsWeb) return;

    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;

    var notificationStatus = await Permission.notification.status;

    if (!notificationStatus.isGranted) {
      notificationStatus = await Permission.notification.request();

      if (!notificationStatus.isGranted && context.mounted) {
        await _showDialog(
          context,
          localizations.notificationPermissionTitle,
          localizations.notificationPermissionMessage,
          localizations.okButton,
        );
      }
      
      notificationStatus = await Permission.notification.request();

      if (!notificationStatus.isGranted && context.mounted) {
        _showDialog(
          context,
          localizations.notificationAccessDeniedTitle,
          localizations.notificationAccessDeniedMessage,
          localizations.okButton,
        );
      }
    }
  }

  static Future<void> _showDialog(
    BuildContext context,
    String title,
    String content,
    String buttonText,
  ) {
    return showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(content),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(buttonText),
          ),
        ],
      ),
    );
  }
}
