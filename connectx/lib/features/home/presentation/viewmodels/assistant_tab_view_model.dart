import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/models/chat_message.dart';
import 'package:connectx/models/app_types.dart';

class AssistantTabViewModel extends ChangeNotifier {
  final SpeechService _speechService;

  AssistantTabViewModel({SpeechService? speechService})
    : _speechService = speechService ?? SpeechService();

  // ── Conversation state ──────────────────────────────────────────────────
  ConversationState _conversationState = ConversationState.idle;
  final List<ChatMessage> _chatMessages = [];
  String _currentMessage = '';
  String _statusText = '';
  bool _lastMessageWasUser = false;
  bool _areCallbacksSetup = false;
  String? _error;

  // ── Session mode ────────────────────────────────────────────────────────
  /// true = voice session (mic active); false = text session (mic muted)
  bool _isVoiceMode = false;

  // ── Connection readiness ─────────────────────────────────────────────────
  /// Guards against concurrent startChat() calls
  bool _isStarting = false;

  /// true once the data channel is confirmed open (safe to send text)
  bool _dataChannelReady = false;

  /// Text message queued before the data channel was ready
  String? _pendingTextMessage;

  // ── Idle timer ───────────────────────────────────────────────────────────
  Timer? _idleTimer;
  static const _idleTimeout = Duration(minutes: 10);

  /// Stored so _handleIdleTimeout can restore the hint text
  String _resetStatusText = '';

  // ── Getters ──────────────────────────────────────────────────────────────
  ConversationState get conversationState => _conversationState;
  List<ChatMessage> get chatMessages => List.unmodifiable(_chatMessages);
  String get currentMessage => _currentMessage;
  String get statusText => _statusText;
  String? get error => _error;
  bool get isVoiceMode => _isVoiceMode;

  // ── Initialisation ───────────────────────────────────────────────────────
  void initialize(String localStatusText, String languageCode) {
    _resetStatusText = localStatusText;
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

  // ── Callback wiring ───────────────────────────────────────────────────────
  void _setupCallbacks() {
    _speechService.onSpeechStart = () {
      _conversationState = ConversationState.connecting;
      // Always start muted; unmuted per mode once the channel is ready
      _speechService.setMicrophoneMuted(true);
      notifyListeners();
    };

    // Update status text when the underlying RTC connection is established.
    // Do NOT call _onDataChannelReady here — RTCPeerConnectionStateConnected
    // fires when ICE+DTLS complete, but the SCTP association (data channel
    // "open") happens slightly after.  Sending the pending text message at this
    // point would reach a not-yet-open channel and be silently dropped by
    // WebRTCService.sendTextMessage, permanently losing the message because
    // _dataChannelReady would already be true when onDataChannelOpen fires.
    _speechService.onConnected = () {
      _statusText = '';
      notifyListeners();
    };

    // Primary gate: data channel explicitly opened
    _speechService.onDataChannelOpen = () {
      _onDataChannelReady();
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
      // Any activity resets the idle timer
      _resetIdleTimer();

      if (isUser) {
        // Dedup: if the last message is an optimistically-added user message
        // with the same text, skip re-adding it (the server echo arrived).
        final alreadyShown = _chatMessages.isNotEmpty &&
            _chatMessages.last.isUser &&
            _chatMessages.last.text == text;
        if (!alreadyShown) {
          _currentMessage = text;
          _chatMessages.add(ChatMessage(text: text, isUser: true));
        }
        _lastMessageWasUser = true;
        // Keep processing state for optimistic UI — onRuntimeState(thinking) is
        // the authoritative source of truth but arrives slightly after the echo.
        _conversationState = ConversationState.processing;
      } else {
        if (_lastMessageWasUser ||
            _chatMessages.isEmpty ||
            _chatMessages.last.isUser) {
          // New AI response starting — let onRuntimeState drive _conversationState;
          // only manage chat messages and mic state here.
          _currentMessage = text;
          _chatMessages.add(ChatMessage(text: text, isUser: false));
          _lastMessageWasUser = false;
          // Unmute mic only for voice sessions when AI responds
          if (_isVoiceMode) {
            _speechService.setMicrophoneMuted(false);
          }
        } else {
          // Append chunk to last AI message
          _currentMessage += text;
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

    _speechService.onRuntimeState = (AgentRuntimeState state) {
      _resetIdleTimer();
      _conversationState = _runtimeStateToConversationState(state);
      notifyListeners();
    };
  }

  /// Maps a backend [AgentRuntimeState] to the UI [ConversationState].
  ConversationState _runtimeStateToConversationState(AgentRuntimeState state) {
    switch (state) {
      case AgentRuntimeState.bootstrap:
      case AgentRuntimeState.dataChannelWait:
        return ConversationState.connecting;
      case AgentRuntimeState.thinking:
      case AgentRuntimeState.llmStreaming:
      case AgentRuntimeState.toolExecuting:
        return ConversationState.processing;
      case AgentRuntimeState.listening:
      case AgentRuntimeState.speaking:
      case AgentRuntimeState.interrupting:
      case AgentRuntimeState.modeSwitch:
        return ConversationState.listening;
      case AgentRuntimeState.errorRetryable:
      case AgentRuntimeState.terminated:
        return ConversationState.idle;
    }
  }

  // ── Data-channel readiness (dual-gate, dedup) ────────────────────────────
  void _onDataChannelReady() {
    if (_dataChannelReady) return; // already handled
    _dataChannelReady = true;

    // Apply correct mic state for the session mode
    if (_isVoiceMode) {
      _speechService.setMicrophoneMuted(false);
    }
    // else: stays muted for text sessions

    // Start idle timer once connected
    _resetIdleTimer();

    // Flush any pending text message
    final pending = _pendingTextMessage;
    _pendingTextMessage = null;
    if (pending != null && pending.trim().isNotEmpty) {
      _sendTextMessageInternal(pending);
    }

    notifyListeners();
  }

  // ── Idle timer ────────────────────────────────────────────────────────────
  void _resetIdleTimer() {
    _idleTimer?.cancel();
    _idleTimer = Timer(_idleTimeout, _handleIdleTimeout);
  }

  void _handleIdleTimeout() {
    debugPrint('AssistantTabViewModel: idle timeout — closing session');
    _idleTimer?.cancel();
    _idleTimer = null;
    try {
      _speechService.stopSpeech();
    } catch (e) {
      debugPrint('Error stopping speech on idle timeout: $e');
    }
    _conversationState = ConversationState.idle;
    _currentMessage = '';
    _chatMessages.clear();
    _statusText = _resetStatusText;
    _isVoiceMode = false;
    _dataChannelReady = false;
    _pendingTextMessage = null;
    _isStarting = false;
    notifyListeners();
  }

  // ── Public session API ────────────────────────────────────────────────────

  /// Start a new session.
  ///
  /// [voiceMode] — true: unmute mic after connection; false: keep mic muted.
  /// [pendingText] — text to send as soon as the data channel is ready.
  Future<void> startChat({bool voiceMode = false, String? pendingText}) async {
    if (_isStarting || _conversationState != ConversationState.idle) return;
    _isStarting = true;
    _isVoiceMode = voiceMode;
    _pendingTextMessage = pendingText;
    _dataChannelReady = false;

    // Optimistic update: show the user's first message immediately so the UI
    // responds before the server echo arrives (which may take a few seconds
    // while WebRTC is being established).
    if (pendingText != null && pendingText.trim().isNotEmpty) {
      _chatMessages.add(ChatMessage(text: pendingText.trim(), isUser: true));
      _lastMessageWasUser = true;
      _conversationState = ConversationState.connecting;
      notifyListeners();
    }

    try {
      await _speechService.startSpeech(mode: voiceMode ? 'voice' : 'text');
    } catch (e) {
      _error = e.toString();
      _statusText = 'Error: $_error';
      _conversationState = ConversationState.idle;
      _isVoiceMode = false;
      _pendingTextMessage = null;
      notifyListeners();
    } finally {
      _isStarting = false;
    }
  }

  /// Stop the session and clear history.
  Future<void> stopChat(String resetStatusText) async {
    _resetStatusText = resetStatusText;
    _idleTimer?.cancel();
    _idleTimer = null;

    try {
      _speechService.stopSpeech();
    } catch (e) {
      debugPrint('Error stopping chat: $e');
    }

    _conversationState = ConversationState.idle;
    _currentMessage = '';
    _chatMessages.clear();
    _statusText = resetStatusText;
    _isVoiceMode = false;
    _dataChannelReady = false;
    _pendingTextMessage = null;
    _isStarting = false;
    notifyListeners();
  }

  /// Switch to text mode: mute mic and tell the server to pause TTS output.
  void switchToTextMode() {
    if (_isVoiceMode) {
      _isVoiceMode = false;
      _speechService.setMicrophoneMuted(true);
      // Notify server so ongoing TTS is interrupted immediately.
      _speechService.notifyModeSwitch('text');
      notifyListeners();
    }
  }

  /// Switch to voice mode: acquire microphone and renegotiate the WebRTC
  /// connection so the server activates the STT + TTS pipeline.
  Future<void> switchToVoiceMode() async {
    if (_isVoiceMode) return;
    _isVoiceMode = true;
    notifyListeners();
    try {
      await _speechService.enableVoiceMode();
    } catch (e) {
      _isVoiceMode = false;
      _error = 'Failed to switch to voice mode: $e';
      notifyListeners();
    }
  }

  // ── Text messaging ────────────────────────────────────────────────────────

  /// Send a text message.  Safe to call only when [_dataChannelReady] is true.
  void sendTextMessage(String text) {
    if (text.trim().isEmpty) return;
    if (!_dataChannelReady) {
      debugPrint(
        'AssistantTabViewModel: data channel not ready, unable to send message',
      );
      _error = 'Unable to send message: connection is not ready yet.';
      notifyListeners();
      return;
    }
    // Optimistic update: add message immediately so UI feels instant.
    _chatMessages.add(ChatMessage(text: text.trim(), isUser: true));
    _lastMessageWasUser = true;
    _conversationState = ConversationState.processing;
    notifyListeners();
    _sendTextMessageInternal(text);
  }

  void _sendTextMessageInternal(String text) {
    try {
      final sent = _speechService.sendTextMessage(text);
      if (!sent) {
        _error = 'Unable to send message: connection is not ready yet.';
        notifyListeners();
        return;
      }
      _resetIdleTimer();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  // ── Error handling ────────────────────────────────────────────────────────
  void clearError() {
    _error = null;
    notifyListeners();
  }

  // ── Dispose ───────────────────────────────────────────────────────────────
  @override
  void dispose() {
    _idleTimer?.cancel();
    _speechService.stopSpeech();
    _speechService.onSpeechStart = null;
    _speechService.onConnected = null;
    _speechService.onDataChannelOpen = null;
    _speechService.onSpeechEnd = null;
    _speechService.onDisconnected = null;
    _speechService.onChatMessage = null;
    super.dispose();
  }
}
