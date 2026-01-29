import 'package:flutter/foundation.dart';
import '../../../../services/speech_service.dart';
import '../../../../models/chat_message.dart';
import '../../../../models/app_types.dart';

class SearchTabViewModel extends ChangeNotifier {
  final SpeechService _speechService;

  SearchTabViewModel({SpeechService? speechService})
      : _speechService = speechService ?? SpeechService();
  
  // State
  ConversationState _conversationState = ConversationState.idle;
  final List<ChatMessage> _chatMessages = [];
  String _currentMessage = '';
  String _statusText = '';
  bool _lastMessageWasUser = false;
  bool _areCallbacksSetup = false;
  String? _error; // For UI to consume (e.g. show dialog)

  // Getters
  ConversationState get conversationState => _conversationState;
  List<ChatMessage> get chatMessages => List.unmodifiable(_chatMessages);
  String get currentMessage => _currentMessage;
  String get statusText => _statusText;
  String? get error => _error;

  // Initialize
  void initialize(String localStatusText, String languageCode) {
    if (_statusText.isEmpty || (_chatMessages.isEmpty && _conversationState == ConversationState.idle)) {
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
      _conversationState = ConversationState.listening;
      notifyListeners();
    };

    _speechService.onConnected = () {
      // Clear status text so chat messages appear immediately
      _statusText = '';
      notifyListeners();
    };

    _speechService.onSpeechEnd = () {
      _conversationState = ConversationState.idle;
      notifyListeners();
    };

    _speechService.onDisconnected = () {
      _conversationState = ConversationState.idle;
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
        if (_lastMessageWasUser || _chatMessages.isEmpty || _chatMessages.last.isUser) {
          // New AI response starting (after user message OR first message OR last was user)
          _currentMessage = text;
          _chatMessages.add(ChatMessage(text: text, isUser: false));
          _lastMessageWasUser = false;
          _conversationState = ConversationState.listening; // AI is speaking
        } else {
          // Appending chunks to existing AI response
          _currentMessage += text;
          // Update the last message in the list
          if (_chatMessages.isNotEmpty && !_chatMessages.last.isUser) {
            _chatMessages[_chatMessages.length - 1] = ChatMessage(text: _currentMessage, isUser: false);
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
