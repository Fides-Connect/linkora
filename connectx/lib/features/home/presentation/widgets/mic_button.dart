import 'package:flutter/material.dart';
import '../../../../models/app_types.dart';
import '../../../../utils/constants.dart';

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
        width: AppConstants.micButtonSize,
        height: AppConstants.micButtonSize,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            colors: state != ConversationState.idle
                ? [Colors.red.shade400, Colors.red.shade700]
                : [AppConstants.primaryCyan, AppConstants.primaryPurple],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [
            BoxShadow(
              color: (state != ConversationState.idle
                  ? Colors.red 
                  : AppConstants.primaryPurple)
                  .withValues(alpha: AppConstants.shadowOpacity),
              blurRadius: AppConstants.shadowBlurRadius,
              spreadRadius: AppConstants.shadowSpreadRadius,
            ),
          ],
        ),
        child: state == ConversationState.connecting
            ? const SizedBox(
                width: 32,
                height: 32,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : Icon(
                state != ConversationState.idle ? Icons.stop : Icons.mic,
                color: Colors.white,
                size: AppConstants.micIconSize,
              ),
      ),
    );
  }
}
