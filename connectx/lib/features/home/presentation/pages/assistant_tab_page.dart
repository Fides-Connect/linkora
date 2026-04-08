import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../core/theme/app_theme_colors.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/app_types.dart';
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
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Called after initState AND whenever an InheritedWidget dependency changes
    // (including locale changes from ConnectXApp.setLocale).  This ensures that
    // _speechService._languageCode is always in sync with the current UI locale
    // so the next session is started with the correct language.
    //
    // Deferred via addPostFrameCallback because didChangeDependencies() fires
    // during _firstBuild (still inside the build phase).  Calling initialize()
    // synchronously here would trigger notifyListeners() during build, which
    // Flutter forbids.
    final vm = context.read<AssistantTabViewModel>();
    final localizations = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context);
    final statusText = vm.voiceEnabled
        ? (localizations?.tapMicrophoneToStart ?? 'Tap microphone to start')
        : '';
    final languageCode = locale.languageCode;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) vm.initialize(statusText, languageCode, aiStatusLabels: localizations?.aiStatusLabels ?? {});
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final vm = context.read<AssistantTabViewModel>();

      // Initialize language and callbacks BEFORE starting the session so that
      // startChat() uses the correct language code from the start.  Without
      // this, initialize() would fire AFTER startChat() (both use
      // addPostFrameCallback; didChangeDependencies registers its callback
      // second), causing a language mismatch that triggers an unnecessary
      // stop-and-restart race.
      final localizations = AppLocalizations.of(context);
      final locale = Localizations.localeOf(context);
      final statusText = vm.voiceEnabled
          ? (localizations?.tapMicrophoneToStart ?? 'Tap microphone to start')
          : '';
      vm.initialize(statusText, locale.languageCode, aiStatusLabels: localizations?.aiStatusLabels ?? {});

      if (vm.voiceEnabled) {
        await PermissionHelper.requestMicrophonePermission(context);
        if (!mounted) return;
        await PermissionHelper.requestNotificationPermission(context);
        if (!mounted) return;
      }

      if (mounted) {
        // Auto-start a text session so the server greets the user by name
        // as soon as the Assistant page opens, without requiring any input.
        await vm.startChat(voiceMode: false);
      }
    });
  }

  void _handleError(String error) {
    final localizations = AppLocalizations.of(context);
    if (localizations == null) return;
    final vm = context.read<AssistantTabViewModel>();
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(localizations.errorTitle),
        content: Text('${localizations.errorOccurred}\n\n$error'),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              vm.clearError();
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
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    // Estimate input row height based on keyboard visibility.
    // With mic button: 20 (top spacing) + 80/48 (mic) + 30/10 (bottom gap)
    // Text-only (no mic): 20 + 50 (text field) + 30/10 (bottom gap)
    final bool showMicButton = viewModel.voiceEnabled;
    final double maxInputRowHeight = showMicButton ? 20.0 + 80.0 + 30.0 : 20.0 + 50.0 + 30.0;
    final double minInputRowHeight = showMicButton ? 20.0 + 48.0 + 10.0 : 20.0 + 50.0 + 10.0;
    final keyboardVisible = MediaQuery.of(context).viewInsets.bottom > 0;
    final inputRowHeight = keyboardVisible ? minInputRowHeight : maxInputRowHeight;
    final chatHeight =
        screenHeight - topPadding - bottomPadding - inputRowHeight;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        behavior: HitTestBehavior.opaque,
        child: SafeArea(
          child: Stack(
            children: [
              const AppBackground(),

              // Fixed AI Visualizer in background (hidden in lite/text-only mode)
              if (viewModel.voiceEnabled)
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
                      state: viewModel.conversationState,
                      toolStatusLabel: viewModel.toolStatusLabel,
                      height: chatHeight > 0 ? chatHeight : 300,
                    ),
                  ),
                  // Session-ended banner: shown after timeout with a "New Session" button
                  if (viewModel.sessionEnded)
                    _SessionEndedBanner(
                      onNewSession: () => viewModel.startChat(voiceMode: false),
                    ),
                  const SizedBox(height: 20),
                  ChatInputRow(
                    state: viewModel.conversationState,
                    isVoiceMode: viewModel.isVoiceMode,
                    showMicButton: viewModel.voiceEnabled,
                    enabled: viewModel.isInputEnabled &&
                        viewModel.conversationState !=
                            ConversationState.processing,
                    hintText:
                        AppLocalizations.of(context)?.typeMessageHint ??
                        'Type a message...',
                    onFocusChanged: (focused) {
                      // Switching to text mode: mute mic once on focus (not per keypress)
                      if (focused) viewModel.switchToTextMode();
                    },
                    onMicTap: () async {
                      final state = viewModel.conversationState;
                      final localizations = AppLocalizations.of(context);
                      final resetText =
                          localizations?.tapMicrophoneToStart ??
                          'Tap microphone to start';

                      if (state == ConversationState.idle) {
                        // Start a voice session
                        await viewModel.startChat(voiceMode: true);
                        if (context.mounted) {
                          final err = viewModel.error;
                          if (err != null) _handleError(err);
                        }
                      } else if (state == ConversationState.connecting &&
                          !viewModel.isVoiceMode) {
                        // Text session is connecting — stop it and start voice
                        HapticFeedback.mediumImpact();
                        final resetText =
                            localizations?.tapMicrophoneToStart ??
                            'Tap microphone to start';
                        await viewModel.stopChat(resetText);
                        await viewModel.startChat(voiceMode: true);
                        if (context.mounted) {
                          final err = viewModel.error;
                          if (err != null) _handleError(err);
                        }
                      } else if (state == ConversationState.connecting &&
                          viewModel.isVoiceMode) {
                        // User aborts a voice session while it's still connecting
                        HapticFeedback.mediumImpact();
                        await viewModel.stopChat(resetText);
                      } else if (!viewModel.isVoiceMode) {
                        // Active text session → switch to voice (acquire mic + renegotiate)
                        await viewModel.switchToVoiceMode();
                        if (context.mounted) {
                          final err = viewModel.error;
                          if (err != null) _handleError(err);
                        }
                      } else {
                        // Active voice session → mute mic, stay in session
                        viewModel.switchToTextMode();
                      }
                    },
                    onTextSubmit: (text) async {
                      if (viewModel.conversationState ==
                          ConversationState.idle) {
                        // Start a text session with the message queued for
                        // delivery once the data channel is ready (no race).
                        await viewModel.startChat(
                          voiceMode: false,
                          pendingText: text,
                        );
                        if (context.mounted) {
                          final err = viewModel.error;
                          if (err != null) _handleError(err);
                        }
                      } else {
                        // Session already alive — send immediately
                        viewModel.sendTextMessage(text);
                      }
                    },
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Banner shown when a session ended (e.g. 10-min idle timeout) with a button
/// to start a fresh session while keeping the previous chat visible above.
class _SessionEndedBanner extends StatelessWidget {
  final VoidCallback onNewSession;
  const _SessionEndedBanner({required this.onNewSession});

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: context.appSurface1,
      child: Row(
        children: [
          Expanded(
            child: Text(
              localizations?.sessionEndedBanner ??
                  'Session ended after 10 minutes of inactivity',
              style: TextStyle(color: context.appSecondaryColor, fontSize: 13),
            ),
          ),
          const SizedBox(width: 12),
          TextButton(
            onPressed: onNewSession,
            style: TextButton.styleFrom(
              foregroundColor: Colors.white,
              backgroundColor: AppConstants.primaryCyan.withValues(alpha: 0.8),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: Text(
              localizations?.newSessionButton ?? 'New Session',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
