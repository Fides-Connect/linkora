import 'package:flutter/material.dart';

class ChatDisplay extends StatelessWidget {
  final String message;
  final String statusText;

  const ChatDisplay({
    super.key,
    required this.message,
    required this.statusText,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      height: 80, // Fixed height for 2 lines
      alignment: Alignment.center,
      child: Text(
        message.isNotEmpty ? message : statusText,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 24,
          fontWeight: FontWeight.w300,
          height: 1.2,
        ),
        textAlign: TextAlign.center,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
