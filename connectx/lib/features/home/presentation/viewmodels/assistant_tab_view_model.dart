import 'dart:async';
import 'dart:collection';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/models/chat_message.dart';
import 'package:connectx/models/app_types.dart';
import 'package:connectx/models/provider_card_data.dart';


class AssistantTabViewModel extends ChangeNotifier with WidgetsBindingObserver {
  final SpeechService _speechService;

  AssistantTabViewModel({SpeechService? speechService})
    : _speechService = speechService ?? SpeechService() {
    WidgetsBinding.instance.addObserver(this);
  }

  // ── Conversation state ──────────────────────────────────────────────────
  ConversationState _conversationState = ConversationState.idle;
  final List<ChatMessage> _chatMessages = [];
  String _currentMessage = '';
  String _statusText = '';
  String _toolStatusLabel = '';
  // Maps English label key → localized label; set on each initialize() call.
  Map<String, String> _aiStatusLabels = {};
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

  /// true once the first AI message has been received.
  /// Prevents the input field from being enabled before the greeting arrives.
  bool _greetingReceived = false;

  /// Text message queued before the data channel was ready
  String? _pendingTextMessage;

  /// Queue of user message texts awaiting a server echo.
  /// When the echo arrives with matching text, we dequeue and skip re-adding it (GAP-4).
  final Queue<String> _pendingEchoTexts = Queue<String>();

  // ── Idle timer ───────────────────────────────────────────────────────────
  Timer? _idleTimer;
  static const _idleTimeout = Duration(minutes: 10);

  /// True after the idle timer fires so the UI can offer a "New Session" button.
  bool _sessionEnded = false;

  /// True while the app is in the background (paused/hidden lifecycle state).
  bool _appInBackground = false;

  /// Set to true when the session dropped while the app was in the background.
  /// The UI shows a "reconnecting" banner instead of the session-ended banner.
  bool _sessionDroppedInBackground = false;

  /// Set to true by [_reconnectSession] so the first AI message on a fresh
  /// server connection (the greeting) is swallowed and not shown in the chat.
  /// The server always greets on connect, but after a reconnect the user should
  /// just see the preserved history and continue — not a second greeting.
  bool _suppressReconnectGreeting = false;

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
  String get toolStatusLabel => _toolStatusLabel;
  String? get error => _error;
  bool get isVoiceMode => _isVoiceMode;
  bool get voiceEnabled => _speechService.voiceEnabled;
  /// True once the data channel is open and the backend can receive messages.
  bool get isSessionReady => _dataChannelReady;
  /// True once the channel is open AND the first AI message has been received.
  /// Use this to gate the chat input field so users cannot type before the
  /// greeting arrives.
  bool get isInputEnabled => _dataChannelReady && _greetingReceived;
  /// True when the session ended (timeout or explicit stop) and chat history is preserved.
  bool get sessionEnded => _sessionEnded;

  /// True when the connection dropped while the app was backgrounded and a
  /// silent reconnect is in progress or pending user confirmation.
  bool get sessionDroppedInBackground => _sessionDroppedInBackground;

  // ── Initialisation ───────────────────────────────────────────────────────
  /// Translates an English status label to the session language.
  /// Falls back to the original [englishLabel] when no translation is found.
  String _t(String englishLabel) => _aiStatusLabels[englishLabel] ?? englishLabel;

  void initialize(String localStatusText, String languageCode, {Map<String, String> aiStatusLabels = const {}}) {
    _aiStatusLabels = aiStatusLabels;
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
      if (_conversationState != ConversationState.idle) {
        // A session is currently active.  The server has already locked that
        // session to the old language (STT config, LLM prompts, TTS voice).
        // Restart immediately so the new language takes effect right away.
        final wasVoiceMode = _isVoiceMode;
        unawaited(_restartForLanguageChange(localStatusText, wasVoiceMode));
      } else {
        // No active session — skip voice-only warmups when the deployment
        // does not support voice (e.g. lite mode).
        if (_speechService.voiceEnabled) {
          unawaited(_speechService.preWarmConnection());
          unawaited(_speechService.warmUpGreeting());
        }
      }
    }
  }

  /// Stops the current session and starts a fresh one in the new language.
  /// Called fire-and-forget from [initialize] when the language changes
  /// while a session is active.
  Future<void> _restartForLanguageChange(
      String statusText, bool voiceMode) async {
    await stopChat(statusText);
    await startChat(voiceMode: voiceMode);
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
      if (_appInBackground && _dataChannelReady) {
        // Connection dropped while the app was in the background.  Mark it so
        // the resume handler can trigger a silent reconnect instead of showing
        // the session-ended banner.
        _sessionDroppedInBackground = true;
        _dataChannelReady = false;
        _greetingReceived = false;
        // Do NOT touch _chatMessages — history must be preserved.
        notifyListeners();
        return;
      }
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
        // Mark that the AI has sent at least one message so the input field
      // becomes available (guarded by isInputEnabled).
      if (!_greetingReceived) {
          _greetingReceived = true;
          // Suppress the server's fresh greeting on a silent reconnect: the user
          // already sees the preserved history, so we don't want "Hello, I'm Elin"
          // appended after their previous conversation.
          if (_suppressReconnectGreeting) {
            _suppressReconnectGreeting = false;
            // Restore the prior conversation history in the server's LLM context
            // so the AI remembers what was discussed before the reconnect.
            _sendHistoryToServer();
            // Clear the reconnecting banner now that the channel confirmed ready.
            _sessionDroppedInBackground = false;
            _conversationState = ConversationState.listening;
            notifyListeners();
            return;
          }
        }

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
      // Provide a contextual label for each processing state so the user
      // can see what the assistant is currently doing instead of plain dots.
      switch (state) {
        case AgentRuntimeState.thinking:
          _toolStatusLabel = _t('Thinking...');
        case AgentRuntimeState.llmStreaming:
          _toolStatusLabel = _t('Composing response...');
        case AgentRuntimeState.toolExecuting:
          // The backend emits a specific label via onToolStatus before this
          // state fires. Only fall back to a generic label if no specific one
          // arrived (e.g. for internal signal_transition calls).
          if (_toolStatusLabel.isEmpty ||
              _toolStatusLabel == _t('Thinking...') ||
              _toolStatusLabel == _t('Composing response...')) {
            _toolStatusLabel = _t('Working...');
          }
        default:
          _toolStatusLabel = '';
      }
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

    _speechService.onToolStatus = (String label) {
      _toolStatusLabel = _t(label);
      notifyListeners();
    };

    _speechService.onVoiceUpgradeTimeout = () {
      // The renegotiation did not produce a remote audio track in time.
      // Revert to text mode so the user is not left without a working session.
      _isVoiceMode = false;
      notifyListeners();
    };

    // Server confirmed we reconnected to the exact same (parked) session.
    // All state is intact on the server — no greeting will come, no history
    // restore is needed.  Simply clear the reconnect flags and let the user
    // continue the conversation.
    _speechService.onSessionResumed = () {
      _suppressReconnectGreeting = false;
      _greetingReceived = true;
      _sessionDroppedInBackground = false;
      _sessionEnded = false;
      _conversationState = ConversationState.listening;
      _resetIdleTimer();
      debugPrint(
        'AssistantTabViewModel: server session resumed — full state preserved, no greeting expected',
      );
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
    // Note: _sessionDroppedInBackground is cleared later in onChatMessage once
    // the server greeting has been suppressed and the channel is confirmed ready.

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

  // ── App lifecycle ─────────────────────────────────────────────────────────
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        _appInBackground = true;
        // Pause the idle timer so it does not expire while the user is away.
        _idleTimer?.cancel();
        _idleTimer = null;
        break;

      case AppLifecycleState.resumed:
        _appInBackground = false;
        if (_sessionDroppedInBackground) {
          // Connection dropped while backgrounded — attempt a silent reconnect.
          _handleBackgroundDisconnect();
        } else if (_dataChannelReady) {
          // Connection survived — simply restart the idle timer.
          _resetIdleTimer();
        }
        break;

      default:
        break;
    }
  }

  /// Called when the app resumes and the WebSocket/WebRTC connection that was
  /// active before backgrounding has been lost.  Reconnects silently without
  /// clearing chat history, and shows a lightweight status banner.
  void _handleBackgroundDisconnect() {
    if (_chatMessages.isEmpty) {
      // Nothing to preserve — start fresh as usual.
      _sessionDroppedInBackground = false;
      unawaited(startChat(voiceMode: false));
      return;
    }
    debugPrint('AssistantTabViewModel: connection dropped in background — reconnecting');
    // Flags may already be set by onDisconnected; ensure consistent state.
    _sessionDroppedInBackground = true;
    _sessionEnded = false;
    _conversationState = ConversationState.connecting;
    _dataChannelReady = false;
    _greetingReceived = false;
    _pendingTextMessage = null;
    _pendingEchoTexts.clear();
    _isStarting = false;
    notifyListeners();
    unawaited(_reconnectSession());
  }

  /// Silently re-establishes the transport without resetting chat history.
  Future<void> _reconnectSession() async {
    if (_isStarting) return;
    _isStarting = true;
    // Mark that the next server greeting should be suppressed so it is not
    // appended to the preserved chat history.
    _suppressReconnectGreeting = true;
    try {
      await _speechService.startSpeech(mode: 'text');
    } catch (e) {
      _error = e.toString();
      _suppressReconnectGreeting = false;
      _conversationState = ConversationState.idle;
      _sessionDroppedInBackground = false;
      _sessionEnded = _chatMessages.isNotEmpty;
      notifyListeners();
    } finally {
      _isStarting = false;
    }
  }

  /// Sends the preserved chat history to the server so the LLM regains context.
  ///
  /// Called after the reconnect greeting is swallowed. The server replaces its
  /// blank LLM session history with these messages, enabling the AI to continue
  /// the conversation as if no disconnect occurred.
  void _sendHistoryToServer() {
    final historyMessages = _chatMessages
        .where((m) => m.text.isNotEmpty && m.cards == null)
        .map((m) => <String, String>{
              'role': m.isUser ? 'user' : 'assistant',
              'text': m.text,
            })
        .toList();
    if (historyMessages.isEmpty) return;
    _speechService.sendRawMessage({
      'type': 'restore-history',
      'messages': historyMessages,
    });
    debugPrint(
      'AssistantTabViewModel: sent restore-history with ${historyMessages.length} message(s)',
    );
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
    _statusText = _resetStatusText;
    _isVoiceMode = false;
    _dataChannelReady = false;
    _greetingReceived = false;
    _pendingTextMessage = null;
    _pendingEchoTexts.clear();
    _isStarting = false;
    _sessionEnded = _chatMessages.isNotEmpty;
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
    _sessionEnded = false;
    _chatMessages.clear();
    _pendingEchoTexts.clear();
    _currentMessage = '';
    _lastMessageWasUser = false;
    _dataChannelReady = false;
    _greetingReceived = false;
    // Always enter connecting immediately so the loading spinner is shown even
    // when there is no pending text (e.g. the auto-started greeting session).
    _conversationState = ConversationState.connecting;
    notifyListeners();

    // Optimistic update: show the user's first message immediately so the UI
    // responds before the server echo arrives (which may take a few seconds
    // while WebRTC is being established).
    if (pendingText != null && pendingText.trim().isNotEmpty) {
      final optimisticMsg = ChatMessage(text: pendingText.trim(), isUser: true);
      _pendingEchoTexts.addLast(optimisticMsg.text);
      _pendingTextMessage = pendingText.trim();
      _chatMessages.add(optimisticMsg);
      _lastMessageWasUser = true;
      notifyListeners();
    }

    try {
      await _speechService.startSpeech(mode: voiceMode ? 'voice' : 'text', newSession: true);
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

  /// Stop the session. Chat history is preserved so the user can review it
  /// and tap "New Session" to start fresh.
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
    _statusText = resetStatusText;
    _isVoiceMode = false;
    _dataChannelReady = false;
    _greetingReceived = false;
    _pendingTextMessage = null;
    _pendingEchoTexts.clear();
    _isStarting = false;
    _sessionEnded = _chatMessages.isNotEmpty;
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

  // ── Test helpers ─────────────────────────────────────────────────────────
  @visibleForTesting
  void triggerIdleTimeoutForTest() => _handleIdleTimeout();

  // ── Dispose ───────────────────────────────────────────────────────────────
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
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
