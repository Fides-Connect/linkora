/// Represents a chat message in the conversation
class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime? timestamp;

  ChatMessage({
    required this.text,
    required this.isUser,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  /// Convert from Map (for backward compatibility)
  factory ChatMessage.fromMap(Map<String, dynamic> map) {
    return ChatMessage(
      text: map['text'] as String,
      isUser: map['isUser'] as bool,
      timestamp: map['timestamp'] != null 
          ? DateTime.parse(map['timestamp'] as String)
          : null,
    );
  }

  /// Convert to Map (for serialization if needed)
  Map<String, dynamic> toMap() {
    return {
      'text': text,
      'isUser': isUser,
      'timestamp': timestamp?.toIso8601String(),
    };
  }

  @override
  String toString() => 'ChatMessage(text: $text, isUser: $isUser, timestamp: $timestamp)';
}
