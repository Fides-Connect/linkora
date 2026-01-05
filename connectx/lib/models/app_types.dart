/// Core type definitions for the application

// ============================================================================
// Enums
// ============================================================================

/// Conversation state enum
enum ConversationState {
  idle,       // Not connected
  listening,  // Connected and listening to user
  processing, // Processing user input (thinking)
}

// ============================================================================
// Callback Type Definitions
// ============================================================================

/// Callback for when speech/conversation starts
typedef OnSpeechStartCallback = void Function();

/// Callback for when speech/conversation ends
typedef OnSpeechEndCallback = void Function();

/// Callback for when connection is established
typedef OnConnectedCallback = void Function();

/// Callback for when connection is lost
typedef OnDisconnectedCallback = void Function();

/// Callback for when a chat message is received
/// Parameters: text, isUser, isChunk
typedef OnChatMessageCallback = void Function(String text, bool isUser, bool isChunk);

/// Callback for locale changes
typedef OnLocaleChangeCallback = void Function(String languageCode);
