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
import '../viewmodels/assistant_tab_view_model.dart';
import '../widgets/ai_neural_visualizer.dart';
import '../widgets/chat_display.dart';
import '../widgets/chat_input_row.dart';

class AssistantTabPage extends StatelessWidget {
  const AssistantTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const _AssistantTabPageContent();
  }
}

class _AssistantTabPageContent extends StatefulWidget {
  const _AssistantTabPageContent();

  @override
  State<_AssistantTabPageContent> createState() =>
      _AssistantTabPageContentState();
}

class _AssistantTabPageContentState extends State<_AssistantTabPageContent> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await PermissionHelper.requestMicrophonePermission(context);
      await PermissionHelper.requestNotificationPermission(context);

      if (mounted) {
        final localizations = AppLocalizations.of(context);
        final locale = Localizations.localeOf(context);
        context.read<AssistantTabViewModel>().initialize(
          localizations?.tapMicrophoneToStart ?? 'Tap microphone to start',
          locale.languageCode,
        );
      }
    });
    _setupForegroundMessageHandler();
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
              context.read<AssistantTabViewModel>().clearError();
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
    final viewModel = context.watch<AssistantTabViewModel>();

    // Calculate available height for chat display
    final screenHeight = MediaQuery.of(context).size.height;
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    final inputRowHeight =
        130.0; // 20 (top spacing) + ~80 (input row) + 30 (bottom spacing)
    final chatHeight =
        screenHeight -
        topPadding -
        bottomPadding -
        inputRowHeight -
        bottomInset;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        behavior: HitTestBehavior.opaque,
        child: SafeArea(
          child: Stack(
            children: [
              const AppBackground(),

              // Fixed AI Visualizer in background
              Positioned(
                top: -50,
                left: 0,
                right: 0,
                child: SizedBox(
                  height: 400,
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
              ),

              // Chat and input overlay
              Column(
                children: [
                  Expanded(
                    child: ChatDisplay(
                      messages: viewModel.chatMessages,
                      statusText: viewModel.statusText,
                      height: chatHeight > 0 ? chatHeight : 300,
                    ),
                  ),
                  const SizedBox(height: 20),
                  ChatInputRow(
                    state: viewModel.conversationState,
                    hintText:
                        AppLocalizations.of(context)?.typeMessageHint ??
                        'Type a message...',
                    onMicTap: () async {
                      if (viewModel.conversationState !=
                          ConversationState.idle) {
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
                    onTextSubmit: (text) {
                      if (viewModel.conversationState ==
                          ConversationState.idle) {
                        // Start conversation first if not already connected
                        viewModel.startChat().then((_) {
                          if (context.mounted) {
                            final err = viewModel.error;
                            if (err != null) {
                              _handleError(err);
                            } else {
                              // Send text message after connection established
                              viewModel.sendTextMessage(text);
                            }
                          }
                        });
                      } else {
                        // Already connected, just send the message
                        viewModel.sendTextMessage(text);
                      }
                    },
                  ),
                  const SizedBox(height: 30),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
