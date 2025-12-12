import 'package:flutter/material.dart';

/// AI conversation text display with fade-in animations
/// Shows the AI's response or the user's transcript
class AIConversationText extends StatefulWidget {
  final String text;
  final bool isListening;
  final bool isProcessing;
  final TextStyle? textStyle;
  final TextStyle? listeningStyle;
  final TextStyle? processingStyle;
  final Duration animationDuration;
  final double minHeight;

  const AIConversationText({
    super.key,
    required this.text,
    this.isListening = false,
    this.isProcessing = false,
    this.textStyle,
    this.listeningStyle,
    this.processingStyle,
    this.animationDuration = const Duration(milliseconds: 400),
    this.minHeight = 100,
  });

  @override
  State<AIConversationText> createState() => _AIConversationTextState();
}

class _AIConversationTextState extends State<AIConversationText>
    with SingleTickerProviderStateMixin {
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;
  String _displayedText = '';

  @override
  void initState() {
    super.initState();
    _displayedText = widget.text;

    _fadeController = AnimationController(
      vsync: this,
      duration: widget.animationDuration,
    );

    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );

    _fadeController.forward();
  }

  @override
  void didUpdateWidget(AIConversationText oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (widget.text != oldWidget.text) {
      // Fade out, change text, fade in
      _fadeController.reverse().then((_) {
        if (mounted) {
          setState(() {
            _displayedText = widget.text;
          });
          _fadeController.forward();
        }
      });
    }
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  TextStyle _getTextStyle() {
    if (widget.isListening && widget.listeningStyle != null) {
      return widget.listeningStyle!;
    } else if (widget.isProcessing && widget.processingStyle != null) {
      return widget.processingStyle!;
    } else if (widget.textStyle != null) {
      return widget.textStyle!;
    }

    // Default styles based on state
    if (widget.isListening) {
      return const TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w300,
        color: Color(0xFFCCCCCC),
        height: 1.5,
      );
    } else if (widget.isProcessing) {
      return const TextStyle(
        fontSize: 14,
        color: Color(0xFF999999),
      );
    } else {
      return const TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w500,
        color: Colors.white,
        height: 1.5,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(minHeight: widget.minHeight),
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: FadeTransition(
        opacity: _fadeAnimation,
        child: _buildContent(),
      ),
    );
  }

  Widget _buildContent() {
    if (widget.isProcessing && _displayedText.isEmpty) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildBouncingDot(0),
          const SizedBox(width: 4),
          _buildBouncingDot(150),
          const SizedBox(width: 4),
          _buildBouncingDot(300),
          const SizedBox(width: 12),
          Text(
            'Thinking...',
            style: _getTextStyle(),
          ),
        ],
      );
    }

    return Text(
      widget.isListening && _displayedText.isEmpty 
          ? 'Listening...' 
          : _displayedText,
      style: _getTextStyle(),
      textAlign: TextAlign.center,
      maxLines: widget.isListening ? null : 5,
      overflow: widget.isListening ? null : TextOverflow.ellipsis,
    );
  }

  Widget _buildBouncingDot(int delayMs) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: Duration(milliseconds: 600 + delayMs),
      curve: Curves.easeInOut,
      builder: (context, value, child) {
        return Transform.translate(
          offset: Offset(0, -4 * (0.5 - (value - 0.5).abs()) * 2),
          child: Container(
            width: 6,
            height: 6,
            decoration: const BoxDecoration(
              color: Color(0xFF00D4FF),
              shape: BoxShape.circle,
            ),
          ),
        );
      },
      onEnd: () {
        // Restart animation
        if (mounted) {
          setState(() {});
        }
      },
    );
  }
}

/// A widget that wraps AIConversationText with quote styling
class AIQuotedConversation extends StatelessWidget {
  final String text;
  final bool isListening;
  final bool isProcessing;
  final double maxWidth;

  const AIQuotedConversation({
    super.key,
    required this.text,
    this.isListening = false,
    this.isProcessing = false,
    this.maxWidth = 400,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!isListening && !isProcessing && text.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Icon(
                Icons.format_quote,
                size: 32,
                color: Colors.white.withOpacity(0.3),
              ),
            ),
          AIConversationText(
            text: text,
            isListening: isListening,
            isProcessing: isProcessing,
            textStyle: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w500,
              color: Colors.white,
              height: 1.5,
            ),
            listeningStyle: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w300,
              color: Color(0xFFCCCCCC),
              height: 1.5,
            ),
            processingStyle: const TextStyle(
              fontSize: 14,
              color: Color(0xFF999999),
            ),
          ),
        ],
      ),
    );
  }
}
