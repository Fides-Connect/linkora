import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme_colors.dart';
import '../../../../models/app_types.dart';
import '../../../../models/chat_message.dart';
import '../../../../utils/constants.dart';
import 'provider_card.dart';

class ChatDisplay extends StatelessWidget {
  final List<ChatMessage> messages;
  final String statusText;
  final ConversationState state;
  final String toolStatusLabel;
  final double? height;

  const ChatDisplay({
    super.key,
    required this.messages,
    required this.statusText,
    required this.state,
    this.toolStatusLabel = '',
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    final displayHeight = height ?? 380;

    // If no messages, show loading spinner or status text
    if (messages.isEmpty) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        height: displayHeight,
        alignment: Alignment.center,
        child: state == ConversationState.connecting
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 36,
                    height: 36,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.5,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        AppConstants.primaryCyan,
                      ),
                    ),
                  ),
                ],
              )
            : Text(
                statusText,
                style: TextStyle(
                  color: context.appPrimaryColor,
                  fontSize: 18,
                  fontWeight: FontWeight.w300,
                  height: 1.2,
                ),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
      );
    }

    // Show chat messages with scrolling and fade effect at top
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      height: displayHeight,
      child: ShaderMask(
        shaderCallback: (Rect bounds) {
          return LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: const [Colors.transparent, Colors.white, Colors.white],
            stops: const [
              0.0,
              0.10,
              1.0,
            ], // Fade out top ~15% (roughly 2 lines)
          ).createShader(bounds);
        },
        blendMode: BlendMode.dstIn,
        child: ListView.builder(
          reverse: true, // Show latest messages at the bottom
          itemCount: messages.length + (state == ConversationState.processing ? 1 : 0),
          itemBuilder: (context, index) {
            // Index 0 (bottom) is the typing indicator when processing
            if (state == ConversationState.processing && index == 0) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 12.0),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: _TypingIndicator(label: toolStatusLabel),
                ),
              );
            }
            // Shift index by 1 when typing indicator is present
            final adjustedIndex = state == ConversationState.processing
                ? index - 1
                : index;
            // Reverse index to show latest messages first (at bottom)
            final reversedIndex = messages.length - 1 - adjustedIndex;
            final message = messages[reversedIndex];
            final isUser = message.isUser;

            // Check if we need extra spacing (30+ seconds gap from previous message)
            bool needsExtraSpacing = false;
            if (reversedIndex > 0) {
              // reversedIndex > 0 guards against the oldest message (reversedIndex == 0)
              // which has no earlier message to compare against.
              final previousMessage = messages[reversedIndex - 1];
              if (message.timestamp != null &&
                  previousMessage.timestamp != null) {
                final timeDiff = message.timestamp!.difference(
                  previousMessage.timestamp!,
                );
                needsExtraSpacing = timeDiff.inSeconds > 30;
              }
            }

            // Provider cards message — render a column of cards, no text bubble
            if (message.cards != null && message.cards!.isNotEmpty) {
              return Padding(
                padding: EdgeInsets.only(
                  bottom: 12.0,
                  top: needsExtraSpacing ? 24.0 : 0.0,
                ),
                child: Column(
                  children: message.cards!
                      .map((card) => ProviderCard(card: card))
                      .toList(),
                ),
              );
            }

            final text = message.text;

            return Padding(
              padding: EdgeInsets.only(
                bottom: 12.0,
                top: needsExtraSpacing ? 24.0 : 0.0,
              ),
              child: Align(
                alignment: isUser
                    ? Alignment.centerRight
                    : Alignment.centerLeft,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16.0,
                    vertical: 10.0,
                  ),
                  decoration: BoxDecoration(
                    color: isUser ? context.appAccent : context.appSurface1,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18),
                      topRight:
                          isUser ? const Radius.circular(4) : const Radius.circular(18),
                      bottomLeft:
                          isUser ? const Radius.circular(18) : const Radius.circular(4),
                      bottomRight: const Radius.circular(18),
                    ),
                  ),
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.75,
                  ),
                  child: Text(
                    text,
                    style: TextStyle(
                      color: isUser ? Colors.white : context.appPrimaryColor,
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      height: 1.4,
                    ),
                    textAlign: isUser ? TextAlign.right : TextAlign.left,
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

/// Animated three-dot typing indicator shown while the AI is processing.
/// When [label] is non-empty a short status text is shown below the dots.
class _TypingIndicator extends StatefulWidget {
  final String label;
  const _TypingIndicator({this.label = ''});

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
      decoration: BoxDecoration(
        color: context.appSurface1,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(4),
          topRight: Radius.circular(18),
          bottomLeft: Radius.circular(18),
          bottomRight: Radius.circular(18),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AnimatedBuilder(
            animation: _controller,
            builder: (context, _) {
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) {
                  final phase = _controller.value * 2 * math.pi - i * (math.pi / 2);
                  final offset = -4.0 * math.sin(phase).clamp(-1.0, 1.0);
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3.0),
                    child: Transform.translate(
                      offset: Offset(0, offset),
                      child: Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: context.appSecondaryColor,
                        ),
                      ),
                    ),
                  );
                }),
              );
            },
          ),
          if (widget.label.isNotEmpty) ...[            const SizedBox(height: 6),
            Text(
              widget.label,
              style: TextStyle(
                color: context.appHintColor,
                fontSize: 13,
                fontWeight: FontWeight.w300,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
