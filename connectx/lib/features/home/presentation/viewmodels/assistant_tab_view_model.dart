import 'package:flutter/foundation.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/models/chat_message.dart';
import 'package:connectx/models/app_types.dart';

class AssistantTabViewModel extends ChangeNotifier {
  final SpeechService _speechService;

  AssistantTabViewModel({SpeechService? speechService})
    : _speechService = speechService ?? SpeechService();

  // State
  ConversationState _conversationState = ConversationState.idle;
  final List<ChatMessage> _chatMessages = [];
  String _currentMessage = '';
  String _statusText = '';
  bool _lastMessageWasUser = false;
  bool _areCallbacksSetup = false;
  String? _error; // For UI to consume (e.g. show dialog)
  bool _isTextInputMode = false; // Track if user is in text input mode

  // Getters
  ConversationState get conversationState => _conversationState;
  List<ChatMessage> get chatMessages => List.unmodifiable(_chatMessages);
  String get currentMessage => _currentMessage;
  String get statusText => _statusText;
  String? get error => _error;
  bool get isTextInputMode => _isTextInputMode;

  // Initialize
  void initialize(String localStatusText, String languageCode) {
    if (_statusText.isEmpty ||
        (_chatMessages.isEmpty &&
            _conversationState == ConversationState.idle)) {
      _statusText = localStatusText;
      notifyListeners();
    }
    _speechService.setLanguageCode(languageCode);

    if (!_areCallbacksSetup) {
      _setupCallbacks();
      _areCallbacksSetup = true;
    }
  }

  void _setupCallbacks() {
    _speechService.onSpeechStart = () {
      _conversationState = ConversationState.connecting;
      // Mute microphone until connection is fully established (AI speaks greeting)
      _speechService.setMicrophoneMuted(true);
      notifyListeners();
    };

    _speechService.onConnected = () {
      // Clear status text so chat messages appear immediately
      _statusText = '';
      notifyListeners();
    };

    _speechService.onSpeechEnd = () {
      _conversationState = ConversationState.idle;
      _speechService.setMicrophoneMuted(false);
      notifyListeners();
    };

    _speechService.onDisconnected = () {
      _conversationState = ConversationState.idle;
      _speechService.setMicrophoneMuted(false);
      notifyListeners();
    };

    _speechService.onChatMessage = (String text, bool isUser, bool isChunk) {
      if (isUser) {
        _currentMessage = text;
        _chatMessages.add(ChatMessage(text: text, isUser: true));
        _lastMessageWasUser = true;
        _conversationState = ConversationState.processing;
      } else {
        // AI Message
        if (_lastMessageWasUser ||
            _chatMessages.isEmpty ||
            _chatMessages.last.isUser) {
          // New AI response starting (after user message OR first message OR last was user)
          _currentMessage = text;
          _chatMessages.add(ChatMessage(text: text, isUser: false));
          _lastMessageWasUser = false;
          _conversationState = ConversationState.listening; // AI is speaking
          // Unmute microphone now that AI is responding (which implies connection is ready)
          _speechService.setMicrophoneMuted(false);
        } else {
          // Appending chunks to existing AI response
          _currentMessage += text;
          // Update the last message in the list
          if (_chatMessages.isNotEmpty && !_chatMessages.last.isUser) {
            _chatMessages[_chatMessages.length - 1] = ChatMessage(
              text: _currentMessage,
              isUser: false,
            );
          }
        }
      }
      notifyListeners();
    };
  }

  Future<void> startChat() async {
    try {
      await _speechService.startSpeech();
    } catch (e) {
      _error = e.toString();
      _statusText = 'Error: $_error';
      _conversationState = ConversationState.idle;
      notifyListeners();
    }
  }

  // Method to clear error after UI has shown it
  void clearError() {
    _error = null;
    notifyListeners();
  }

  Future<void> stopChat(String resetStatusText) async {
    try {
      _speechService.stopSpeech();
    } catch (e) {
      debugPrint('Error stopping chat: $e');
    }

    _conversationState = ConversationState.idle;
    _currentMessage = '';
    _chatMessages.clear();
    _statusText = resetStatusText;
    _isTextInputMode = false;
    notifyListeners();
  }

  /// Send text message to AI assistant
  ///
  /// This method is called when user submits text input.
  /// It mutes the microphone and sends the text directly to the server.
  void sendTextMessage(String text) {
    if (text.trim().isEmpty) return;

    try {
      // Send the text message via speech service
      _speechService.sendTextMessage(text);

      // The message will be echoed back by the server via data channel
      // and handled by the onChatMessage callback, so we don't add it here
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  /// Handle text field focus changes
  ///
  /// When text field is focused, switch to text input mode and mute microphone.
  /// When focus is lost, switch back to voice mode if not in an active conversation.
  void onTextFieldFocusChanged(bool hasFocus) {
    _isTextInputMode = hasFocus;

    if (hasFocus && _conversationState != ConversationState.idle) {
      // User wants to type - mute microphone but keep connection active
      _speechService.setMicrophoneMuted(true);
    }

    notifyListeners();
  }

  /// Handle microphone button tap
  ///
  /// When tapped during text input mode, this will unmute the microphone
  /// and start recording immediately.
  Future<void> onMicButtonTap() async {
    if (_conversationState != ConversationState.idle) {
      // Stop the conversation
      return;
    }

    // Starting voice input - unmute microphone and start speech
    _isTextInputMode = false;
    _speechService.setMicrophoneMuted(false);
    notifyListeners();
  }

  @override
  void dispose() {
    _speechService.stopSpeech();
    _speechService.onSpeechStart = null;
    _speechService.onConnected = null;
    _speechService.onSpeechEnd = null;
    _speechService.onDisconnected = null;
    _speechService.onChatMessage = null;
    super.dispose();
  }
}
