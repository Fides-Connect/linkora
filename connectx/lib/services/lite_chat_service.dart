import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'wrappers.dart';
import '../models/app_types.dart';

/// Lite-mode WebSocket chat client for the AI-Assistant ``/ws/chat`` endpoint.
///
/// Unlike [WebRTCService], there is no WebRTC peer connection here — the
/// WebSocket IS the transport.  Messages use the same JSON protocol as the
/// DataChannel in full mode:
///
/// * Outbound (client → server): ``{"type": "text-input", "text": "…"}``
/// * Inbound  (server → client): ``{"type": "chat", …}`` |
///                                ``{"type": "runtime-state", …}`` |
///                                ``{"type": "provider-cards", …}``
///
/// Auth:
/// * On ``wss://`` (non-web): ``Authorization: Bearer <token>`` header.
/// * On ``ws://`` or web: first-message ``{"type": "auth", "token": "…"}``.
///
/// Callbacks mirror [WebRTCService] so [SpeechService] can use either without
/// changes to the ViewModel.
class LiteChatService {
  // ── State ──────────────────────────────────────────────────────────────────
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  bool _isConnected = false;

  /// Messages sent before the connection was ready are queued here and
  /// flushed once [onDataChannelOpen] fires.
  final List<String> _pendingMessages = [];

  /// True once the server has confirmed auth and the session is active.
  bool _sessionReady = false;

  // ── Idle timer (mirrors server-side 10-minute timeout) ─────────────────────
  Timer? _idleTimer;
  static const _idleTimeout = Duration(minutes: 10);

  // ── Dependencies (injected for testability) ────────────────────────────────
  final String _languageCode;
  final bool _isSecure;
  final String _serverUrl;
  final FirebaseAuthWrapper _firebaseAuthWrapper;
  final WebSocketChannel Function(Uri, Map<String, dynamic>) _webSocketFactory;

  // ── Callbacks ──────────────────────────────────────────────────────────────
  Function()? onConnected;
  Function()? onDisconnected;
  Function(String)? onError;
  /// Fires when the session is active and text messages can be sent.
  /// Mirrors [WebRTCService.onDataChannelOpen].
  Function()? onDataChannelOpen;
  OnChatMessageCallback? onChatMessage;
  OnRuntimeStateCallback? onRuntimeState;
  OnProviderCardsCallback? onProviderCards;

  // ── Constructor ────────────────────────────────────────────────────────────

  LiteChatService({
    FirebaseAuthWrapper? firebaseAuthWrapper,
    WebSocketChannel Function(Uri, Map<String, dynamic>)? webSocketFactory,
    String? languageCode,
    String? serverUrl,
  }) : _firebaseAuthWrapper = firebaseAuthWrapper ?? FirebaseAuthWrapper(),
       _webSocketFactory = webSocketFactory ?? _defaultWebSocketFactory,
       _languageCode = languageCode ?? 'de',
       _isSecure = _detectSecure(serverUrl),
       _serverUrl = _buildWsUrl(serverUrl);

  static bool _detectSecure(String? rawServer) {
    final s = rawServer ?? dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? '';
    return s.startsWith('wss://') || s.startsWith('https://');
  }

  static String _buildWsUrl(String? rawServer) {
    final s = rawServer ?? dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? '';
    if (s.startsWith('wss://')) return '$s/ws/chat';
    if (s.startsWith('https://')) return s.replaceFirst('https://', 'wss://') + '/ws/chat';
    if (s.startsWith('ws://')) return '$s/ws/chat';
    if (s.startsWith('http://')) return s.replaceFirst('http://', 'ws://') + '/ws/chat';
    return 'ws://$s/ws/chat'; // bare host:port — local dev
  }

  static WebSocketChannel _defaultWebSocketFactory(
    Uri uri,
    Map<String, dynamic> headers,
  ) {
    if (kIsWeb) {
      return WebSocketChannel.connect(uri);
    }
    return IOWebSocketChannel.connect(uri, headers: headers);
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  bool get isConnected => _isConnected;

  /// Open the WebSocket connection to ``/ws/chat``.
  ///
  /// If [_isSecure] → attaches ``Authorization: Bearer`` header.
  /// Otherwise → sends first-message auth.
  Future<void> connect() async {
    if (_isConnected) return;

    final uri = Uri.parse('$_serverUrl?language=$_languageCode');
    debugPrint('LiteChatService: connecting to $uri');

    Map<String, dynamic> headers = {};
    bool useFirstMessageAuth = false;

    if (_isSecure && !kIsWeb) {
      final token = await _firebaseAuthWrapper.getIdToken();
      if (token != null && token.isNotEmpty) {
        headers = {'Authorization': 'Bearer $token'};
      } else {
        debugPrint('LiteChatService: no auth token available — aborting connect');
        onError?.call('No authentication token');
        return;
      }
    } else {
      useFirstMessageAuth = true;
    }

    try {
      _channel = _webSocketFactory(uri, headers);
      _isConnected = true;

      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onWsError,
        onDone: _onWsDone,
        cancelOnError: false,
      );

      if (useFirstMessageAuth) {
        await _sendFirstMessageAuth();
      } else {
        // With header auth the server accepts the connection immediately;
        // treat the channel as session-ready.
        _markSessionReady();
      }

      onConnected?.call();
      debugPrint('LiteChatService: WebSocket connected');
    } catch (e) {
      _isConnected = false;
      debugPrint('LiteChatService: connect() failed: $e');
      onError?.call(e.toString());
    }
  }

  /// Disconnect and tear down the WebSocket connection.
  Future<void> disconnect() async {
    _idleTimer?.cancel();
    _idleTimer = null;

    await _subscription?.cancel();
    _subscription = null;

    await _channel?.sink.close();
    _channel = null;

    _isConnected = false;
    _sessionReady = false;
    _pendingMessages.clear();
  }

  /// Send a text message to the AI assistant.
  ///
  /// If the session is not yet fully ready, the message is queued and sent
  /// once [onDataChannelOpen] fires.
  void sendTextMessage(String text) {
    if (text.trim().isEmpty) return;
    if (!_sessionReady) {
      _pendingMessages.add(text);
      return;
    }
    _send({'type': 'text-input', 'text': text});
    _resetIdleTimer();
  }

  // ── Private ────────────────────────────────────────────────────────────────

  Future<void> _sendFirstMessageAuth() async {
    final token = await _firebaseAuthWrapper.getIdToken();
    if (token == null || token.isEmpty) {
      debugPrint('LiteChatService: no auth token — sending unauthenticated');
    } else {
      _send({'type': 'auth', 'token': token});
    }
    // Server will respond with {"type": "auth-ok"} or close; we treat the
    // connection as ready immediately for local dev (no close received).
    // For full auth validation the server sends "auth-ok" then "chat" frames.
    _markSessionReady();
  }

  void _markSessionReady() {
    _sessionReady = true;
    _resetIdleTimer();
    onDataChannelOpen?.call();
    _flushPendingMessages();
  }

  void _flushPendingMessages() {
    if (_pendingMessages.isEmpty) return;
    final pending = List<String>.from(_pendingMessages);
    _pendingMessages.clear();
    for (final text in pending) {
      _send({'type': 'text-input', 'text': text});
    }
  }

  void _send(Map<String, dynamic> payload) {
    if (_channel == null || !_isConnected) {
      debugPrint('LiteChatService: cannot send — not connected');
      return;
    }
    _channel!.sink.add(jsonEncode(payload));
  }

  void _onMessage(dynamic raw) {
    _resetIdleTimer();
    Map<String, dynamic> msg;
    try {
      msg = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (e) {
      debugPrint('LiteChatService: failed to parse message: $e');
      return;
    }

    final type = msg['type'] as String?;
    switch (type) {
      case 'auth-ok':
        debugPrint('LiteChatService: auth confirmed by server');
        // Session already marked ready in _sendFirstMessageAuth; no-op here.
        break;

      case 'chat':
        final text = msg['text'] as String? ?? '';
        final isUser = msg['isUser'] as bool? ?? false;
        final isChunk = msg['isChunk'] as bool? ?? false;
        onChatMessage?.call(text, isUser, isChunk);

      case 'runtime-state':
        final rawState = msg['runtimeState'] as String?;
        if (rawState != null) {
          final state = AgentRuntimeState.tryParse(rawState);
          if (state != null) onRuntimeState?.call(state);
        }

      case 'provider-cards':
        final cards = (msg['cards'] as List<dynamic>?)
            ?.whereType<Map<String, dynamic>>()
            .toList();
        if (cards != null) onProviderCards?.call(cards);

      default:
        debugPrint('LiteChatService: unknown message type: $type');
    }
  }

  void _onWsError(Object error, StackTrace st) {
    debugPrint('LiteChatService: WebSocket error: $error');
    onError?.call(error.toString());
  }

  void _onWsDone() {
    debugPrint('LiteChatService: WebSocket closed');
    _isConnected = false;
    _sessionReady = false;
    _idleTimer?.cancel();
    _idleTimer = null;
    onDisconnected?.call();
  }

  // ── Idle timer ─────────────────────────────────────────────────────────────

  void _resetIdleTimer() {
    _idleTimer?.cancel();
    _idleTimer = Timer(_idleTimeout, () {
      debugPrint('LiteChatService: idle timeout — disconnecting');
      disconnect().then((_) => onDisconnected?.call());
    });
  }
}
