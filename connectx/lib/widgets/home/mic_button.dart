import 'package:flutter/material.dart';
import '../../main.dart'; // For ConversationState enum

class MicButton extends StatelessWidget {
  final ConversationState state;
  final VoidCallback onTap;

  const MicButton({
    super.key,
    required this.state,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 80,
        height: 80,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            colors: state != ConversationState.idle
                ? [Colors.red.shade400, Colors.red.shade700]
                : [const Color(0xFF00D4FF), const Color(0xFF6C63FF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [
            BoxShadow(
              color: (state != ConversationState.idle
                  ? Colors.red 
                  : const Color(0xFF6C63FF))
                  .withValues(alpha: 0.4),
              blurRadius: 30,
              spreadRadius: 5,
            ),
          ],
        ),
        child: Icon(
          state != ConversationState.idle ? Icons.stop : Icons.mic,
          color: Colors.white,
          size: 36,
        ),
      ),
    );
  }
}
