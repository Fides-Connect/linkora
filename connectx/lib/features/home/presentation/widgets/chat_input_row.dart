import 'package:flutter/material.dart';
import '../../../../models/app_types.dart';
import '../../../../utils/constants.dart';

/// Combined chat input widget with microphone button and text field
///
/// Animates between two states:
/// - Default: Large microphone button (80x80) prominently displayed, small text field
/// - Text focused: Small microphone button (48x48) on left, expanded text field
class ChatInputRow extends StatefulWidget {
  final ConversationState state;
  final bool isVoiceMode;
  final bool showMicButton;
  final VoidCallback onMicTap;
  final Function(String) onTextSubmit;
  final Function(bool)? onFocusChanged;
  final String hintText;

  const ChatInputRow({
    super.key,
    required this.state,
    required this.isVoiceMode,
    this.showMicButton = true,
    required this.onMicTap,
    required this.onTextSubmit,
    this.onFocusChanged,
    required this.hintText,
  });

  @override
  State<ChatInputRow> createState() => _ChatInputRowState();
}

class _ChatInputRowState extends State<ChatInputRow> {
  final TextEditingController _textController = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  bool _isTextFieldFocused = false;

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(_onFocusChange);
    _textController.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _focusNode.removeListener(_onFocusChange);
    _focusNode.dispose();
    _textController.removeListener(_onTextChanged);
    _textController.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {}); // Rebuild so suffixIcon visibility reflects current text
  }

  void _onFocusChange() {
    setState(() {
      _isTextFieldFocused = _focusNode.hasFocus;
    });
    // Notify the page once per focus change (not per keypress)
    widget.onFocusChanged?.call(_focusNode.hasFocus);
  }

  void _handleTextSubmit() {
    final text = _textController.text.trim();
    if (text.isNotEmpty) {
      widget.onTextSubmit(text);
      _textController.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    // Calculate sizes based on focus state
    final micSize = _isTextFieldFocused ? 48.0 : AppConstants.micButtonSize;
    final micIconSize = _isTextFieldFocused ? 24.0 : AppConstants.micIconSize;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppConstants.defaultPadding,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.start,
            children: [
              // Microphone button - animates size and position (hidden in text-only/lite mode)
              if (widget.showMicButton) AnimatedContainer(
                duration: AppConstants.defaultTransitionDuration,
                curve: Curves.easeInOut,
                width: micSize,
                height: micSize,
                child: GestureDetector(
                  onTap: () {
                    // Unfocus text field and dismiss keyboard when switching to voice
                    _focusNode.unfocus();
                    widget.onMicTap();
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors:
                            widget.isVoiceMode
                            ? [Colors.red.shade400, Colors.red.shade700]
                            : [
                                AppConstants.primaryCyan,
                                AppConstants.primaryPurple,
                              ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color:
                              (widget.isVoiceMode
                                      ? Colors.red
                                      : AppConstants.primaryPurple)
                                  .withValues(
                                    alpha: AppConstants.shadowOpacity,
                                  ),
                          blurRadius: _isTextFieldFocused
                              ? 15.0
                              : AppConstants.shadowBlurRadius,
                          spreadRadius: _isTextFieldFocused
                              ? 2.0
                              : AppConstants.shadowSpreadRadius,
                        ),
                      ],
                    ),
                    child: (widget.state == ConversationState.connecting &&
                            widget.isVoiceMode)
                        ? Center(
                            child: SizedBox(
                              width: micSize * 0.4,
                              height: micSize * 0.4,
                              child: const CircularProgressIndicator(
                                strokeWidth: 3,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  Colors.white,
                                ),
                              ),
                            ),
                          )
                        : Icon(
                            widget.isVoiceMode
                                ? Icons.mic_off
                                : Icons.mic,
                            color: Colors.white,
                            size: micIconSize,
                          ),
                  ),
                ),
              ),

              if (widget.showMicButton) AnimatedContainer(
                duration: AppConstants.defaultTransitionDuration,
                curve: Curves.easeInOut,
                width: _isTextFieldFocused ? 12.0 : 20.0,
              ),

              // Text field - expands via maxLines, no wrapping AnimatedContainer
              Expanded(
                child: TextField(
                  controller: _textController,
                  focusNode: _focusNode,
                  onTap: () {
                    _focusNode.requestFocus();
                  },
                  maxLines: _isTextFieldFocused ? 5 : 1,
                  minLines: 1,
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                  decoration: InputDecoration(
                    hintText: widget.hintText,
                    hintStyle: TextStyle(
                      color: Colors.white.withValues(alpha: 0.5),
                      fontSize: 16,
                    ),
                    filled: true,
                    fillColor: Colors.white.withValues(alpha: 0.1),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: _isTextFieldFocused ? 16.0 : 12.0,
                      vertical: _isTextFieldFocused ? 12.0 : 14.0,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide(
                        color: Colors.white.withValues(alpha: 0.2),
                        width: 1,
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide(
                        color: AppConstants.primaryCyan.withValues(alpha: 0.6),
                        width: 2,
                      ),
                    ),
                    suffixIcon:
                        _isTextFieldFocused && _textController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(
                              Icons.send,
                              color: AppConstants.primaryCyan,
                            ),
                            onPressed: _handleTextSubmit,
                          )
                        : null,
                  ),
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _handleTextSubmit(),
                ),
              ),
            ],
          ),
        ),
        // Bottom gap: animates from 30px → 2px when text field is focused,
        // mirroring the mic button resize animation
        AnimatedContainer(
          duration: AppConstants.defaultTransitionDuration,
          curve: Curves.easeInOut,
          height: _isTextFieldFocused ? 10.0 : 30.0,
        ),
      ],
    );
  }
}
