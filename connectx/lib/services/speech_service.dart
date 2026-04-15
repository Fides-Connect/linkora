import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';
import 'lite_chat_service.dart';
import 'webrtc_service.dart';
import 'wrappers.dart';
import '../models/app_types.dart';

/// Speech service that uses WebRTC to communicate with the AI-Assistant server
/// The server handles Speech-to-Text, LLM processing, and Text-to-Speech
class SpeechService {
  // WebRTC service for server communication
  WebRTCService? _webrtcService;

  // Lite-mode direct WebSocket chat service (used when voiceEnabled == false)
  LiteChatService? _liteChatService;

  // Remote audio renderer for WebRTC audio playback
  RTCVideoRenderer? _remoteRenderer;

  // Dependencies
  final PermissionWrapper _permissionWrapper;
  final FirebaseAuthWrapper _firebaseAuthWrapper;
  final WebRTCService Function(String) _webRTCServiceFactory;
  final LiteChatService Function(String) _liteChatServiceFactory;

  // Language configuration
  String _languageCode = 'de';

  /// True when APP_MODE=full (default). Set APP_MODE=lite in .env to disable
  /// voice pre-warming and mic handling for lite-mode deployments.
  final bool voiceEnabled;

  // Callbacks
  OnSpeechStartCallback? onSpeechStart;
  OnSpeechEndCallback? onSpeechEnd;
  OnConnectedCallback? onConnected;
  OnDisconnectedCallback? onDisconnected;
  OnChatMessageCallback? onChatMessage;
  OnRuntimeStateCallback? onRuntimeState;
  Function()? onDataChannelOpen;
  OnProviderCardsCallback? onProviderCards;
  OnToolStatusCallback? onToolStatus;
  /// Called when the voice upgrade (renegotiation) timed out without receiving
  /// a remote audio track. The UI should revert to text mode.
  Function()? onVoiceUpgradeTimeout;

  static bool _readVoiceEnabled() {
    try {
      return dotenv.env['APP_MODE']?.toLowerCase() != 'lite';
    } catch (_) {
      return true; // dotenv not loaded (e.g. in unit tests) → default full
    }
  }

  SpeechService({
    PermissionWrapper? permissionWrapper,
    WebRTCService Function(String)? webRTCServiceFactory,
    LiteChatService Function(String)? liteChatServiceFactory,
    FirebaseAuthWrapper? firebaseAuthWrapper,
    bool? voiceEnabled,
  }) : _permissionWrapper = permissionWrapper ?? PermissionWrapper(),
       _webRTCServiceFactory =
           webRTCServiceFactory ??
           ((lang) => WebRTCService(languageCode: lang)),
       _liteChatServiceFactory =
           liteChatServiceFactory ??
           ((lang) => LiteChatService(languageCode: lang)),
       _firebaseAuthWrapper = firebaseAuthWrapper ?? FirebaseAuthWrapper(),
       voiceEnabled = voiceEnabled ?? _readVoiceEnabled();

  /// Set the language code for the AI Assistant
  void setLanguageCode(String languageCode) {
    _languageCode = languageCode;
  }

  /// Pre-warm the WebSocket signaling connection and fetch ICE credentials.
  ///
  /// Call this as soon as the user opens the assistant tab.  By the time they
  /// tap the mic button the WebRTC handshake overhead (~300–500 ms) is already
  /// done.  Safe to call without awaiting — failures are silently absorbed.
  Future<void> preWarmConnection() async {
    if (_webrtcService == null) {
      _initializeWebRTC();
    }
    try {
      await _webrtcService!.preWarm();
    } catch (e) {
      debugPrint('SpeechService: preWarmConnection failed (non-critical): $e');
    }
  }

  /// Pre-generate the personalised greeting (LLM + TTS) on the server.
  ///
  /// Calls ``POST /api/v1/assistant/greet-warmup`` so the server caches the
  /// greeting audio before the user taps the mic.  When the voice session
  /// starts the server plays the cached audio immediately (~0 ms) instead of
  /// running LLM + TTS live (~1.5–2.5 s).
  ///
  /// Safe to call without awaiting — failures are silently absorbed.
  Future<void> warmUpGreeting() async {
    try {
      final rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
      if (rawServer == null || rawServer.isEmpty) return;

      final httpBase = _toHttpUrl(rawServer);
      final uri = Uri.parse('$httpBase/api/v1/assistant/greet-warmup');

      final idToken = await _firebaseAuthWrapper.getIdToken();
      if (idToken == null || idToken.isEmpty) return;

      final response = await http.post(
        uri,
        headers: {'Authorization': 'Bearer $idToken'},
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        debugPrint('SpeechService: warmUpGreeting got HTTP ${response.statusCode}');
      } else {
        debugPrint('SpeechService: Greeting warmup triggered');
      }
    } catch (e) {
      debugPrint('SpeechService: warmUpGreeting failed (non-critical): $e');
    }
  }

  /// Convert a raw server URL (as stored in [AI_ASSISTANT_SERVER_URL]) to an
  /// HTTP/HTTPS base URL, normalising the scheme (ws→http, wss→https).
  ///
  /// In release builds, plain HTTP and bare-host URLs are rejected to prevent
  /// Firebase ID tokens from being sent over unencrypted connections.
  static String _toHttpUrl(String raw) {
    // Secure schemes — always allowed.
    if (raw.startsWith('https://')) return raw;
    if (raw.startsWith('wss://')) return raw.replaceFirst('wss://', 'https://');

    // Insecure schemes — only permitted in non-release (local dev) builds.
    if (kReleaseMode) {
      throw StateError(
        'AI_ASSISTANT_SERVER_URL must use https:// or wss:// in release builds. '
        'Got: $raw',
      );
    }
    if (raw.startsWith('http://')) return raw;
    if (raw.startsWith('ws://')) return raw.replaceFirst('ws://', 'http://');
    return 'http://$raw'; // bare host:port — local dev only
  }

  /// Check if microphone is currently muted
  bool get isMicrophoneMuted => _webrtcService?.isMicrophoneMuted ?? true;

  void setMicrophoneMuted(bool muted) {
    _webrtcService?.setMicrophoneMuted(muted);
  }

  void stopSpeech() async {
    // Lite mode
    if (!voiceEnabled) {
      // Null the reference synchronously (before any await) so a concurrent
      // startChat() creating a new _liteChatService is never overwritten by
      // the deferred null assignment from a previous stopSpeech() call.
      final toDisconnect = _liteChatService;
      _liteChatService = null;
      await toDisconnect?.disconnect();
      return;
    }

    // Stop and clean up WebRTC service
    _webrtcService?.disconnect();
    _webrtcService = null;

    // Stop and clean up audio renderer
    if (_remoteRenderer != null) {
      _remoteRenderer!.srcObject = null;
      await _remoteRenderer!.dispose();
      _remoteRenderer = null;
    }
  }

  /// Start speech session by connecting to AI-Assistant server via WebRTC
  /// The server will handle audio streaming, STT, LLM, and TTS processing
  ///
  /// Set [newSession] to ``true`` when the user explicitly starts a fresh
  /// session so the server discards any parked session and sends a greeting.
  Future<void> startSpeech({String mode = 'voice', bool newSession = false}) async {
    if (!voiceEnabled) {
      await _startLiteChat(newSession: newSession);
      return;
    }

    onSpeechStart?.call();

    try {
      // Initialize audio player and WebRTC
      await _initialize(mode: mode);

      // Connect to AI-Assistant server
      await _webrtcService!.connect(mode: mode);

      debugPrint('SpeechService: Connected to AI-Assistant server');
    } catch (e) {
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> _startLiteChat({bool newSession = false}) async {
    onSpeechStart?.call();
    try {
      _initializeLiteChat();
      await _liteChatService!.connect(newSession: newSession);
      debugPrint('SpeechService: LiteChat connected to AI-Assistant server');
    } catch (e) {
      onSpeechEnd?.call();
      rethrow;
    }
  }

  void _initializeLiteChat() {
    _liteChatService = _liteChatServiceFactory(_languageCode);

    _liteChatService!.onConnected = () {
      debugPrint('SpeechService: LiteChat connected');
      onConnected?.call();
    };

    _liteChatService!.onDisconnected = () {
      debugPrint('SpeechService: LiteChat disconnected');
      onDisconnected?.call();
      onSpeechEnd?.call();
    };

    _liteChatService!.onError = (String error) {
      debugPrint('SpeechService: LiteChat error: $error');
      onSpeechEnd?.call();
    };

    _liteChatService!.onChatMessage = (String text, bool isUser, bool isChunk) {
      onChatMessage?.call(text, isUser, isChunk);
    };

    _liteChatService!.onRuntimeState = (AgentRuntimeState state) {
      onRuntimeState?.call(state);
    };

    _liteChatService!.onProviderCards = (List<Map<String, dynamic>> cards) {
      onProviderCards?.call(cards);
    };

    _liteChatService!.onToolStatus = (String label) {
      onToolStatus?.call(label);
    };

    _liteChatService!.onDataChannelOpen = () {
      debugPrint('SpeechService: LiteChat session ready');
      onDataChannelOpen?.call();
    };

    _liteChatService!.onSessionResumed = () {
      debugPrint('SpeechService: LiteChat session resumed on server');
      onSessionResumed?.call();
    };
  }

  Future<void> _initialize({String mode = 'voice'}) async {
    // Microphone permission is only needed for voice mode
    if (mode == 'voice') {
      final microphoneRequest = await _permissionWrapper.requestMicrophone();
      if (!microphoneRequest.isGranted) {
        throw Exception('Microphone permission denied');
      }
    }

    // Initialize WebRTC service
    if (_webrtcService == null) {
      _initializeWebRTC();
    }
  }

  void _initializeWebRTC() {
    _webrtcService = _webRTCServiceFactory(_languageCode);

    // Set up WebRTC callbacks
    _webrtcService!.onConnected = () async {
      debugPrint('SpeechService: WebRTC connected');
      onConnected?.call();
    };

    _webrtcService!.onDisconnected = () {
      debugPrint('SpeechService: WebRTC disconnected');
      onDisconnected?.call();
      onSpeechEnd?.call();
    };

    _webrtcService!.onChatMessage = (String text, bool isUser, bool isChunk) {
      onChatMessage?.call(text, isUser, isChunk);
    };

    _webrtcService!.onRuntimeState = (AgentRuntimeState state) {
      onRuntimeState?.call(state);
    };

    _webrtcService!.onProviderCards = (List<Map<String, dynamic>> cards) {
      onProviderCards?.call(cards);
    };

    _webrtcService!.onToolStatus = (String label) {
      onToolStatus?.call(label);
    };

    _webrtcService!.onRemoteStream = (MediaStream stream) {
      debugPrint('SpeechService: Received remote audio stream');
      unawaited(_handleRemoteStream(stream));
    };

    _webrtcService!.onDataChannelOpen = () {
      debugPrint('SpeechService: Data channel open');
      onDataChannelOpen?.call();
    };

    _webrtcService!.onError = (String error) {
      debugPrint('SpeechService: WebRTC error: $error');
      onSpeechEnd?.call();
    };

    _webrtcService!.onVoiceUpgradeTimeout = () {
      debugPrint('SpeechService: Voice upgrade timed out');
      onVoiceUpgradeTimeout?.call();
    };
  }

  /// Handle incoming remote audio stream from AI-Assistant server
  /// This stream contains the processed audio (STT -> LLM -> TTS)
  Future<void> _handleRemoteStream(MediaStream stream) async {
    debugPrint('SpeechService: Setting up remote audio stream playback');

    try {
      // Get the audio track
      final audioTracks = stream.getAudioTracks();
      if (audioTracks.isEmpty) {
        debugPrint('SpeechService: No audio tracks in remote stream');
        return;
      }

      final audioTrack = audioTracks[0];
      debugPrint(
        'SpeechService: Got remote audio track: ${audioTrack.id}, enabled: ${audioTrack.enabled}, muted: ${audioTrack.muted}',
      );

      // Clean up any existing renderer
      if (_remoteRenderer != null) {
        debugPrint('SpeechService: Disposing existing renderer');
        _remoteRenderer!.srcObject = null;
        await _remoteRenderer!.dispose();
      }

      // Create and initialize an RTCVideoRenderer to handle the audio stream
      debugPrint('SpeechService: Creating new RTCVideoRenderer');
      _remoteRenderer = RTCVideoRenderer();
      await _remoteRenderer!.initialize();
      debugPrint('SpeechService: Renderer initialized');

      // Set the remote stream to the renderer
      _remoteRenderer!.srcObject = stream;
      debugPrint('SpeechService: Remote stream assigned to renderer');

      // Ensure the audio track is enabled and not muted
      audioTrack.enabled = true;
    } catch (e) {
      debugPrint('SpeechService: Error handling remote stream: $e');
      debugPrint('SpeechService: Stack trace: ${StackTrace.current}');
    }
  }

  /// Send text message to the AI Assistant via data channel
  ///
  /// This allows text input to be sent directly to the server,
  /// bypassing the speech-to-text step
  ///
  /// [text] - The text message to send
  /// [messageId] - Optional stable ID for echo deduplication (GAP-4).
  /// Returns `true` if the message was dispatched, `false` if the service is not ready.
  bool sendTextMessage(String text, {String? messageId}) {
    if (!voiceEnabled) {
      if (_liteChatService == null) {
        debugPrint(
          'SpeechService: Cannot send text message, LiteChat service not initialized',
        );
        return false;
      }
      _liteChatService!.sendTextMessage(text);
      return true;
    }

    if (_webrtcService == null) {
      debugPrint(
        'SpeechService: Cannot send text message, WebRTC service not initialized',
      );
      return false;
    }
    _webrtcService!.sendTextMessage(text, messageId: messageId);
    return true;
  }

  /// Fires when the server confirms the client reconnected to a parked session.
  Function()? onSessionResumed;

  /// Send a raw JSON payload to the server (lite mode only).
  ///
  /// Used for control messages such as ``restore-history`` that are not
  /// normal user text input and should not go through the text queue.
  void sendRawMessage(Map<String, dynamic> payload) {
    _liteChatService?.sendRaw(payload);
  }

  /// Notify the server of a mode switch over the data channel.
  ///
  /// Call when the audio pipeline already exists (voice pause/resume)
  /// so no WebRTC renegotiation is needed.
  void notifyModeSwitch(String mode) {
    _webrtcService?.sendModeSwitch(mode);
  }

  /// Release the microphone so the OS clears the mic-in-use indicator.
  ///
  /// Removes the audio track from the WebRTC connection and disposes the
  /// local audio stream.  Call when switching from voice to text mode.
  Future<void> stopVoiceMode() async {
    await _webrtcService?.stopVoiceMode();
  }

  /// Upgrade the current text session to voice mode by acquiring the
  /// microphone and renegotiating the WebRTC connection.
  Future<void> enableVoiceMode() async {
    if (_webrtcService == null) {
      debugPrint('SpeechService: Cannot enable voice mode – service not initialized');
      return;
    }
    final microphoneRequest = await _permissionWrapper.requestMicrophone();
    if (!microphoneRequest.isGranted) {
      throw Exception('Microphone permission denied');
    }
    await _webrtcService!.enableVoiceMode();
  }
}
