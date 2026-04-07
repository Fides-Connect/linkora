import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/services/lite_chat_service.dart';
import 'package:connectx/models/app_types.dart';
import '../helpers/test_helpers.mocks.dart';

void main() {
  late MockWebSocketChannel mockChannel;
  late MockWebSocketSink mockSink;
  late MockFirebaseAuthWrapper mockAuth;
  late StreamController<dynamic> streamController;

  LiteChatService buildService({
    String serverUrl = 'ws://localhost:8080',
  }) =>
      LiteChatService(
        firebaseAuthWrapper: mockAuth,
        webSocketFactory: (uri, headers) => mockChannel,
        languageCode: 'en',
        serverUrl: serverUrl,
      );

  setUp(() {
    streamController = StreamController<dynamic>.broadcast();
    mockChannel = MockWebSocketChannel();
    mockSink = MockWebSocketSink();
    mockAuth = MockFirebaseAuthWrapper();

    when(mockChannel.stream).thenAnswer((_) => streamController.stream);
    when(mockChannel.sink).thenReturn(mockSink);
    when(mockSink.add(any)).thenReturn(null);
    when(mockSink.close()).thenAnswer((_) async {
      if (!streamController.isClosed) await streamController.close();
    });

    when(mockAuth.getIdToken()).thenAnswer((_) async => 'test-token-123');
  });

  tearDown(() async {
    if (!streamController.isClosed) await streamController.close();
  });

  // ══════════════════════════════════════════════════════════════════════════
  // connect() — URL construction
  // ══════════════════════════════════════════════════════════════════════════

  group('LiteChatService URL construction', () {
    test('ws:// server appends /ws/chat', () async {
      final captured = <Uri>[];
      final svc = LiteChatService(
        firebaseAuthWrapper: mockAuth,
        webSocketFactory: (uri, headers) {
          captured.add(uri);
          return mockChannel;
        },
        languageCode: 'en',
        serverUrl: 'ws://localhost:8080',
      );
      await svc.connect();
      expect(captured.first.toString(), contains('/ws/chat'));
      expect(captured.first.queryParameters['language'], 'en');
    });

    test('http:// server maps to ws://', () async {
      final captured = <Uri>[];
      final svc = LiteChatService(
        firebaseAuthWrapper: mockAuth,
        webSocketFactory: (uri, headers) {
          captured.add(uri);
          return mockChannel;
        },
        languageCode: 'de',
        serverUrl: 'http://localhost:8080',
      );
      await svc.connect();
      expect(captured.first.scheme, 'ws');
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // connect() — insecure (ws://) uses first-message auth
  // ══════════════════════════════════════════════════════════════════════════

  group('LiteChatService insecure connect', () {
    test('sends first-message auth with token', () async {
      final svc = buildService();
      await svc.connect();

      final first = verify(mockSink.add(captureAny)).captured.first as String;
      final msg = jsonDecode(first) as Map<String, dynamic>;
      expect(msg['type'], 'auth');
      expect(msg['token'], 'test-token-123');
    });

    test('fires onDataChannelOpen after first-message auth', () async {
      final svc = buildService();
      var opened = false;
      svc.onDataChannelOpen = () => opened = true;

      await svc.connect();

      expect(opened, isTrue);
    });

    test('fires onConnected after connect', () async {
      final svc = buildService();
      var connected = false;
      svc.onConnected = () => connected = true;

      await svc.connect();

      expect(connected, isTrue);
    });

    test('isConnected is true after connect', () async {
      final svc = buildService();
      await svc.connect();
      expect(svc.isConnected, isTrue);
    });

    test('second connect() call is a no-op', () async {
      final svc = buildService();
      await svc.connect();
      await svc.connect();
      // getIdToken should have been called exactly once (first connect only).
      verify(mockAuth.getIdToken()).called(1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // sendTextMessage
  // ══════════════════════════════════════════════════════════════════════════

  group('LiteChatService sendTextMessage', () {
    test('sends correct JSON frame when session is ready', () async {
      final svc = buildService();
      await svc.connect();
      // Sink has the auth frame already; reset captured calls.
      clearInteractions(mockSink);

      svc.sendTextMessage('hello');

      final sent = verify(mockSink.add(captureAny)).captured.single as String;
      final msg = jsonDecode(sent) as Map<String, dynamic>;
      expect(msg['type'], 'text-input');
      expect(msg['text'], 'hello');
    });

    test('empty text is ignored', () async {
      final svc = buildService();
      await svc.connect();
      clearInteractions(mockSink);

      svc.sendTextMessage('   ');

      verifyNever(mockSink.add(any));
    });

    test('message before connect is queued and flushed on open', () async {
      final svc = buildService();
      // Queue message before opening
      svc.sendTextMessage('queued');

      await svc.connect();

      final calls = verify(mockSink.add(captureAny)).captured;
      // calls[0]: auth  calls[1]: queued text
      expect(calls.length, 2);
      final textMsg = jsonDecode(calls[1] as String) as Map<String, dynamic>;
      expect(textMsg['type'], 'text-input');
      expect(textMsg['text'], 'queued');
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // Inbound message dispatch
  // ══════════════════════════════════════════════════════════════════════════

  group('LiteChatService inbound messages', () {
    test('chat message fires onChatMessage', () async {
      final svc = buildService();
      String? gotText;
      bool? gotIsUser;
      bool? gotIsChunk;
      svc.onChatMessage = (t, u, c) {
        gotText = t;
        gotIsUser = u;
        gotIsChunk = c;
      };
      await svc.connect();

      streamController.add(jsonEncode({
        'type': 'chat',
        'text': 'Hi there',
        'isUser': false,
        'isChunk': true,
      }));
      await Future.delayed(Duration.zero);

      expect(gotText, 'Hi there');
      expect(gotIsUser, isFalse);
      expect(gotIsChunk, isTrue);
    });

    test('runtime-state message fires onRuntimeState', () async {
      final svc = buildService();
      AgentRuntimeState? gotState;
      svc.onRuntimeState = (s) => gotState = s;
      await svc.connect();

      streamController
          .add(jsonEncode({'type': 'runtime-state', 'runtimeState': 'listening'}));
      await Future.delayed(Duration.zero);

      expect(gotState, AgentRuntimeState.listening);
    });

    test('unknown runtime state is silently ignored', () async {
      final svc = buildService();
      AgentRuntimeState? gotState;
      svc.onRuntimeState = (s) => gotState = s;
      await svc.connect();

      streamController.add(
          jsonEncode({'type': 'runtime-state', 'runtimeState': 'unknown_xyz'}));
      await Future.delayed(Duration.zero);

      expect(gotState, isNull);
    });

    test('provider-cards message fires onProviderCards', () async {
      final svc = buildService();
      List<Map<String, dynamic>>? gotCards;
      svc.onProviderCards = (c) => gotCards = c;
      await svc.connect();

      streamController.add(jsonEncode({
        'type': 'provider-cards',
        'cards': [
          {'id': '1', 'name': 'Alice'}
        ]
      }));
      await Future.delayed(Duration.zero);

      expect(gotCards, hasLength(1));
      expect(gotCards!.first['name'], 'Alice');
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // disconnect
  // ══════════════════════════════════════════════════════════════════════════

  group('LiteChatService disconnect', () {
    test('isConnected becomes false after disconnect', () async {
      final svc = buildService();
      await svc.connect();
      expect(svc.isConnected, isTrue);

      await svc.disconnect();
      expect(svc.isConnected, isFalse);
    });

    test('fires onDisconnected when server closes', () async {
      final svc = buildService();
      var disconnected = false;
      svc.onDisconnected = () => disconnected = true;
      await svc.connect();

      await streamController.close();
      await Future.delayed(Duration.zero);

      expect(disconnected, isTrue);
    });
  });
}
