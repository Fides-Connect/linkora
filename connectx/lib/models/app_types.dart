/// Core type definitions for the application
library;

// ============================================================================
// Enums
// ============================================================================

/// Conversation state enum
enum ConversationState {
  idle,       // Not connected
  connecting, // Connection in progress
  listening,  // Connected and listening to user
  processing, // Processing user input (thinking)
}

/// Agent runtime state — mirrors the backend AgentRuntimeState enum.
/// Sent over the DataChannel as `{"type": "runtime-state", "runtimeState": "<value>"}`.
enum AgentRuntimeState {
  bootstrap,
  dataChannelWait,
  listening,
  thinking,
  llmStreaming,
  toolExecuting,
  speaking,
  interrupting,
  modeSwitch,
  errorRetryable,
  terminated;

  /// Parse a snake_case string from the backend into the enum value.
  /// Returns null for unknown values so callers can decide how to handle them.
  static AgentRuntimeState? tryParse(String raw) {
    const map = {
      'bootstrap': AgentRuntimeState.bootstrap,
      'data_channel_wait': AgentRuntimeState.dataChannelWait,
      'listening': AgentRuntimeState.listening,
      'thinking': AgentRuntimeState.thinking,
      'llm_streaming': AgentRuntimeState.llmStreaming,
      'tool_executing': AgentRuntimeState.toolExecuting,
      'speaking': AgentRuntimeState.speaking,
      'interrupting': AgentRuntimeState.interrupting,
      'mode_switch': AgentRuntimeState.modeSwitch,
      'error_retryable': AgentRuntimeState.errorRetryable,
      'terminated': AgentRuntimeState.terminated,
    };
    return map[raw];
  }
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

/// Callback for when the backend runtime FSM changes state.
typedef OnRuntimeStateCallback = void Function(AgentRuntimeState state);

/// Callback for when provider cards are received from the backend.
/// Each card is a raw JSON map; parsing to a typed model is done upstream.
typedef OnProviderCardsCallback = void Function(List<Map<String, dynamic>> cards);

/// Callback for when the backend emits a tool-status label.
/// The label is a short human-readable string describing the current operation,
/// e.g. "Searching for providers" or "Submitting your request".
typedef OnToolStatusCallback = void Function(String label);

/// Callback for locale changes
typedef OnLocaleChangeCallback = void Function(String languageCode);
