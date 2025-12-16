import 'package:flutter/material.dart';

class ChatDisplay extends StatelessWidget {
  final List<Map<String, dynamic>> messages;
  final String statusText;

  const ChatDisplay({
    super.key,
    required this.messages,
    required this.statusText,
  });

  @override
  Widget build(BuildContext context) {
    // If no messages, show status text
    if (messages.isEmpty) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        height: 320,
        alignment: Alignment.center,
        child: Text(
          statusText,
          style: const TextStyle(
            color: Colors.white,
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

    // Show chat messages with scrolling
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      height: 320,
      child: ListView.builder(
        reverse: true, // Show latest messages at the bottom
        itemCount: messages.length,
        itemBuilder: (context, index) {
          // Reverse index to show latest messages first (at bottom)
          final reversedIndex = messages.length - 1 - index;
          final message = messages[reversedIndex];
          final text = message['text'] as String;
          final isUser = message['isUser'] as bool;

          return Padding(
            padding: const EdgeInsets.only(bottom: 12.0),
            child: Text(
              text,
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: isUser ? FontWeight.w400 : FontWeight.w300,
                fontStyle: isUser ? FontStyle.italic : FontStyle.normal,
                height: 1.2,
              ),
              textAlign: isUser ? TextAlign.right : TextAlign.left,
            ),
          );
        },
      ),
    );
  }
}
