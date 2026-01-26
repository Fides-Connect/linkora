import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:provider/provider.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/app_types.dart';
import '../../../../services/notification_service.dart';
import '../../../../utils/constants.dart';
import '../../../../utils/permission_helper.dart';
import '../viewmodels/home_view_model.dart';
import '../widgets/ai_neural_visualizer.dart';
import '../widgets/chat_display.dart';
import '../widgets/mic_button.dart';

class AiAssistantPage extends StatelessWidget {
  const AiAssistantPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const _AiAssistantPageContent();
  }
}

class _AiAssistantPageContent extends StatefulWidget {
  const _AiAssistantPageContent();

  @override
  State<_AiAssistantPageContent> createState() =>
      _AiAssistantPageContentState();
}

class _AiAssistantPageContentState extends State<_AiAssistantPageContent> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await PermissionHelper.requestMicrophonePermission(context);
      await PermissionHelper.requestNotificationPermission(context);
    });

    _setupForegroundMessageHandler();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final localizations = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context);
    context.read<HomeViewModel>().initialize(
          localizations?.tapMicrophoneToStart ?? 'Tap microphone to start',
          locale.languageCode,
        );
  }

  void _setupForegroundMessageHandler() {
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      debugPrint('Foreground message received: ${message.messageId}');
      debugPrint('Title: ${message.notification?.title}');
      debugPrint('Body: ${message.notification?.body}');

      if (message.notification != null) {
        final notification = message.notification!;
        final notificationId =
            message.messageId?.hashCode ??
            DateTime.now().millisecondsSinceEpoch;
        NotificationService().showNotification(
          id: notificationId,
          title: notification.title ?? 'New Message',
          body: notification.body ?? '',
        );
      }
    });

    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      debugPrint('Notification opened from background: ${message.messageId}');
    });
  }

  void _handleError(String error) {
    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(localizations.errorTitle),
        content: Text('${localizations.errorOccurred}\n\n$error'),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<HomeViewModel>().clearError();
            },
            child: Text(localizations.okButton),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Watch the VM state
    final viewModel = context.watch<HomeViewModel>();

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),

            Column(
              children: [
                Expanded(
                  child: Center(
                    child: AINeuralVisualizer(
                      isListening:
                          viewModel.conversationState ==
                          ConversationState.listening,
                      isProcessing:
                          viewModel.conversationState ==
                          ConversationState.processing,
                      size: AppConstants.neuralVisualizerSize,
                      primaryColor: AppConstants.primaryCyan,
                      secondaryColor: AppConstants.primaryPurple,
                      accentColor: AppConstants.accentPurple,
                    ),
                  ),
                ),
                ChatDisplay(
                  messages: viewModel.chatMessages,
                  statusText: viewModel.statusText,
                ),
                const SizedBox(height: 40),
                MicButton(
                  state: viewModel.conversationState,
                  onTap: () async {
                    if (viewModel.conversationState != ConversationState.idle) {
                      HapticFeedback.mediumImpact();
                      final localizations = AppLocalizations.of(context);
                      await viewModel.stopChat(
                        localizations?.tapMicrophoneToStart ??
                            'Tap microphone to start',
                      );
                    } else {
                      await viewModel.startChat();
                      if (context.mounted) {
                        final err = viewModel.error;
                        if (err != null) {
                          _handleError(err);
                        }
                      }
                    }
                  },
                ),
                const SizedBox(height: 60),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
