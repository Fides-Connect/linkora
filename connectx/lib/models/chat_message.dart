import 'package:uuid/uuid.dart';
import 'provider_card_data.dart';

/// Generates a new UUID v4.
final _uuid = Uuid();

/// Represents a chat message in the conversation
class ChatMessage {
  final String id;
  final String text;
  final bool isUser;
  final DateTime? timestamp;
  /// Provider cards attached to this message. When non-null, the message is
  /// a cards-only bubble rendered by ChatDisplay instead of a text bubble.
  final List<ProviderCardData>? cards;

  ChatMessage({
    String? id,
    required this.text,
    required this.isUser,
    DateTime? timestamp,
    this.cards,
  })  : id = id ?? _uuid.v4(),
        timestamp = timestamp ?? DateTime.now();

  /// Convert from Map (for backward compatibility)
  factory ChatMessage.fromMap(Map<String, dynamic> map) {
    return ChatMessage(
      id: map['id'] as String?,
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
      'id': id,
      'text': text,
      'isUser': isUser,
      'timestamp': timestamp?.toIso8601String(),
    };
  }

  @override
  String toString() => 'ChatMessage(id: $id, text: $text, isUser: $isUser, timestamp: $timestamp)';
}
