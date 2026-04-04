import 'dart:async';
import 'dart:collection';
import 'package:flutter/foundation.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/models/chat_message.dart';
import 'package:connectx/models/app_types.dart';
import 'package:connectx/models/provider_card_data.dart';


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

  /// Queue of user message texts awaiting a server echo.
  /// When the echo arrives with matching text, we dequeue and skip re-adding it (GAP-4).
  final Queue<String> _pendingEchoTexts = Queue<String>();

  // ── Idle timer ───────────────────────────────────────────────────────────
  Timer? _idleTimer;
  static const _idleTimeout = Duration(minutes: 10);

  /// Deduplication guard: tracks the language for which warmup was last
  /// triggered.  Prevents re-firing warmup on every [initialize] call (which
  /// can happen on every rebuild) while still re-firing when the UI language
  /// actually changes.
  String? _warmupLanguage;

  /// Stored so _handleIdleTimeout can restore the hint text
  String _resetStatusText = '';

  // ── Getters ──────────────────────────────────────────────────────────────
  ConversationState get conversationState => _conversationState;
  List<ChatMessage> get chatMessages => List.unmodifiable(_chatMessages);
  String get currentMessage => _currentMessage;
  String get statusText => _statusText;
  String? get error => _error;
  bool get isVoiceMode => _isVoiceMode;
  bool get voiceEnabled => _speechService.voiceEnabled;
  /// True once the data channel is open and the backend can receive messages.
  bool get isSessionReady => _dataChannelReady;

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

    // Fire-and-forget warmup whenever the language changes (including the
    // first call).  This pre-warms the WebSocket connection AND pre-generates
    // the greeting (LLM + TTS) so both are ready by the time the user taps
    // the mic button.
    if (_warmupLanguage != languageCode) {
      _warmupLanguage = languageCode;
      // Skip voice-only warmups when the deployment does not support voice
      // (e.g. lite mode).  preWarm() is a voice ICE optimisation;
      // warmUpGreeting() pre-generates TTS audio — neither is useful for
      // text-only sessions and the failed pre-warm can race with the live
      // text session if its cleanup fires late.
      if (_speechService.voiceEnabled) {
        unawaited(_speechService.preWarmConnection());
        unawaited(_speechService.warmUpGreeting());
      }
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
        // GAP-4: Text-based dedup — skip re-adding a user message whose echo we
        // already showed optimistically (identified by _pendingEchoTexts queue).
        if (_pendingEchoTexts.isNotEmpty && text == _pendingEchoTexts.first) {
          _pendingEchoTexts.removeFirst(); // consume the pending echo slot
        } else {
          _currentMessage = text;
          _chatMessages.add(ChatMessage(text: text, isUser: true));
        }
        _lastMessageWasUser = true;
        // Keep processing state for optimistic UI — onRuntimeState(thinking) is
        // the authoritative source of truth but arrives slightly after the echo.
        _conversationState = ConversationState.processing;
      } else {
        if (!isChunk ||
            _lastMessageWasUser ||
            _chatMessages.isEmpty ||
            _chatMessages.last.isUser) {
          // New AI response starting — clear processing state immediately so the
          // typing indicator disappears as soon as the first text arrives,
          // without waiting for the onRuntimeState(speaking) backend event.
          if (_conversationState == ConversationState.processing) {
            _conversationState = ConversationState.listening;
          }
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

    _speechService.onProviderCards = (List<Map<String, dynamic>> rawCards) {
      _resetIdleTimer();
      final cards = rawCards
          .map((m) => ProviderCardData.fromJson(m))
          .toList();
      if (cards.isNotEmpty) {
        _chatMessages.add(
          ChatMessage(text: '', isUser: false, cards: cards),
        );
        notifyListeners();
      }
    };

    _speechService.onVoiceUpgradeTimeout = () {
      // The renegotiation did not produce a remote audio track in time.
      // Revert to text mode so the user is not left without a working session.
      _isVoiceMode = false;
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
    _pendingEchoTexts.clear();
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
    if (voiceMode && !_speechService.voiceEnabled) voiceMode = false;
    _isVoiceMode = voiceMode;
    if (pendingText == null || pendingText.trim().isEmpty) {
      _pendingTextMessage = null;
    }
    // Clear history from any prior session so each new session begins with a
    // clean slate and previous greetings / messages are not shown again.
    _chatMessages.clear();
    _pendingEchoTexts.clear();
    _currentMessage = '';
    _lastMessageWasUser = false;
    notifyListeners();
    // _pendingTextMessage set above in the optimistic block when pendingText is non-null
    _dataChannelReady = false;

    // Optimistic update: show the user's first message immediately so the UI
    // responds before the server echo arrives (which may take a few seconds
    // while WebRTC is being established).
    if (pendingText != null && pendingText.trim().isNotEmpty) {
      final optimisticMsg = ChatMessage(text: pendingText.trim(), isUser: true);
      _pendingEchoTexts.addLast(optimisticMsg.text);
      _pendingTextMessage = pendingText.trim();
      _chatMessages.add(optimisticMsg);
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
    _pendingEchoTexts.clear();
    _isStarting = false;
    notifyListeners();
  }

  /// Switch to text mode: mute mic and tell the server to pause TTS output.
  void switchToTextMode() {
    if (_isVoiceMode) {
      _isVoiceMode = false;
      // Notify the server first so it can interrupt TTS immediately, then
      // release the hardware so the OS clears the Android mic indicator.
      _speechService.notifyModeSwitch('text');
      unawaited(_speechService.stopVoiceMode());
      notifyListeners();
    }
  }

  /// Switch to voice mode: acquire microphone and renegotiate the WebRTC
  /// connection so the server activates the STT + TTS pipeline.
  Future<void> switchToVoiceMode() async {
    if (_isVoiceMode || !_speechService.voiceEnabled) return;
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
    // GAP-4: Track the text so the server echo can be deduplicated.
    final optimisticMsg = ChatMessage(text: text.trim(), isUser: true);
    _pendingEchoTexts.addLast(optimisticMsg.text);
    // Optimistic update: add message immediately so UI feels instant.
    _chatMessages.add(optimisticMsg);
    _lastMessageWasUser = true;
    _conversationState = ConversationState.processing;
    notifyListeners();
    _sendTextMessageInternal(text, messageId: optimisticMsg.id);
  }

  void _sendTextMessageInternal(String text, {String? messageId}) {
    try {
      final sent = _speechService.sendTextMessage(text, messageId: messageId);
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
    _speechService.onProviderCards = null;
    super.dispose();
  }
}
