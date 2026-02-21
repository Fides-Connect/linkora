import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:connectx/services/webrtc_service.dart';
import 'package:connectx/services/audio_routing_service.dart';
import 'package:connectx/models/app_types.dart';
import '../helpers/test_helpers.mocks.dart';
import '../helpers/test_constants.dart';
import '../mocks/mock_audio_hardware_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // ── Shared setup ──────────────────────────────────────────────────────────

  late MockWebRTCWrapper mockWebRTCWrapper;
  late MockWebSocketChannel mockWebSocketChannel;
  late MockWebSocketSink mockWebSocketSink;
  late MockFirebaseAuthWrapper mockFirebaseAuthWrapper;
  late MockUser mockUser;
  late MockRTCPeerConnection mockPeerConnection;
  late MockMediaStream mockLocalStream;
  late MockMediaStreamTrack mockAudioTrack;
  late MockRTCDataChannel mockDataChannel;
  late MockAudioHardwareController mockAudioHardwareController;
  late StreamController<dynamic> streamController;

  WebRTCService _buildService() => WebRTCService(
        webRTCWrapper: mockWebRTCWrapper,
        webSocketFactory: (uri) => mockWebSocketChannel,
        audioRoutingServiceFactory: () => AudioRoutingService(
          hardwareController: mockAudioHardwareController,
          deviceCheckInterval: testDeviceCheckInterval,
          inputChangeDebounce: testInputChangeDebounce,
        ),
        firebaseAuthWrapper: mockFirebaseAuthWrapper,
        serverUrl: 'localhost:8000',
      );

  setUp(() async {
    streamController = StreamController<dynamic>.broadcast();
    mockWebRTCWrapper = MockWebRTCWrapper();
    mockWebSocketChannel = MockWebSocketChannel();
    mockWebSocketSink = MockWebSocketSink();
    mockFirebaseAuthWrapper = MockFirebaseAuthWrapper();
    mockUser = MockUser();
    mockPeerConnection = MockRTCPeerConnection();
    mockLocalStream = MockMediaStream();
    mockAudioTrack = MockMediaStreamTrack();
    mockDataChannel = MockRTCDataChannel();
    mockAudioHardwareController = MockAudioHardwareController();

    when(mockWebSocketChannel.sink).thenReturn(mockWebSocketSink);
    when(mockWebSocketChannel.stream)
        .thenAnswer((_) => streamController.stream);
    when(mockWebSocketSink.close()).thenAnswer((_) async {
      if (!streamController.isClosed) await streamController.close();
    });

    when(mockFirebaseAuthWrapper.currentUser).thenReturn(mockUser);
    when(mockUser.uid).thenReturn('test_user_id');

    when(mockWebRTCWrapper.getUserMedia(any))
        .thenAnswer((_) async => mockLocalStream);
    when(mockLocalStream.getAudioTracks()).thenReturn([mockAudioTrack]);
    when(mockAudioTrack.id).thenReturn('audio_track_id');
    when(mockWebRTCWrapper.createPeerConnection(any, any))
        .thenAnswer((_) async => mockPeerConnection);
    when(mockWebRTCWrapper.createPeerConnection(any))
        .thenAnswer((_) async => mockPeerConnection);

    when(mockPeerConnection.addTrack(any, any))
        .thenAnswer((_) async => MockRTCRtpSender());
    when(mockPeerConnection.createOffer(any))
        .thenAnswer((_) async => RTCSessionDescription('offer_sdp', 'offer'));
    when(mockPeerConnection.setLocalDescription(any))
        .thenAnswer((_) async {});
    when(mockPeerConnection.close()).thenAnswer((_) async {});
    when(mockPeerConnection.createDataChannel(any, any))
        .thenAnswer((_) async => mockDataChannel);

    when(mockDataChannel.onMessage = any).thenReturn(null);
    when(mockDataChannel.onDataChannelState = any).thenReturn(null);

    when(mockPeerConnection.onIceCandidate = any).thenReturn(null);
    when(mockPeerConnection.onConnectionState = any).thenReturn(null);
    when(mockPeerConnection.onTrack = any).thenReturn(null);

    when(mockLocalStream.getTracks()).thenReturn([mockAudioTrack]);
    when(mockLocalStream.dispose()).thenAnswer((_) async {});
    when(mockAudioTrack.stop()).thenAnswer((_) async {});
    when(mockPeerConnection.setRemoteDescription(any))
        .thenAnswer((_) async {});
    when(mockPeerConnection.addCandidate(any)).thenAnswer((_) async => true);
    when(mockAudioTrack.enabled = any).thenReturn(null);
  });

  tearDown(() async {
    // Guard against already-closed controller
    if (!streamController.isClosed) {
      await streamController.close();
    }
  });

  // ══════════════════════════════════════════════════════════════════════════
  // connect() — mode parameter
  // ══════════════════════════════════════════════════════════════════════════

  group('WebRTCService connect() mode parameter', () {
    test('voice mode creates local audio stream', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      await svc.connect(mode: 'voice');

      verify(mockWebRTCWrapper.getUserMedia(any)).called(1);
    });

    test('text mode skips local audio stream creation', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      await svc.connect(mode: 'text');

      verifyNever(mockWebRTCWrapper.getUserMedia(any));
    });

    test('text mode does not add local audio track to peer connection', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      await svc.connect(mode: 'text');

      verifyNever(mockPeerConnection.addTrack(any, any));
    });

    test('invalid mode defaults to voice', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      // 'invalid' is not in {'voice','text'} — should fall back to voice
      await svc.connect(mode: 'invalid');

      // Voice path: getUserMedia must be called
      verify(mockWebRTCWrapper.getUserMedia(any)).called(1);
    });

    test('mode is passed as query parameter in the signaling WS URI', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      final capturedUris = <Uri>[];
      // Re-create with URI-capturing factory
      final capturingSvc = WebRTCService(
        webRTCWrapper: mockWebRTCWrapper,
        webSocketFactory: (uri) {
          capturedUris.add(uri);
          return mockWebSocketChannel;
        },
        audioRoutingServiceFactory: () => AudioRoutingService(
          hardwareController: mockAudioHardwareController,
          deviceCheckInterval: testDeviceCheckInterval,
          inputChangeDebounce: testInputChangeDebounce,
        ),
        firebaseAuthWrapper: mockFirebaseAuthWrapper,
        serverUrl: 'ws://localhost:8000',
      );
      addTearDown(capturingSvc.disconnect);

      await capturingSvc.connect(mode: 'text');

      expect(capturedUris, isNotEmpty);
      expect(capturedUris.first.queryParameters['mode'], 'text');
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // onDataChannelOpen callback
  // ══════════════════════════════════════════════════════════════════════════

  group('WebRTCService onDataChannelOpen', () {
    test('fires when data channel state transitions to open', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      bool fired = false;
      svc.onDataChannelOpen = () => fired = true;

      // Capture the onDataChannelState setter
      Function(RTCDataChannelState)? stateCallback;
      when(mockDataChannel.onDataChannelState = any).thenAnswer((inv) {
        stateCallback = inv.positionalArguments.first
            as Function(RTCDataChannelState)?;
      });

      await svc.connect(mode: 'text');

      stateCallback?.call(RTCDataChannelState.RTCDataChannelOpen);

      expect(fired, isTrue);
    });

    test('fires only once even if state fires twice', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      int count = 0;
      svc.onDataChannelOpen = () => count++;

      Function(RTCDataChannelState)? stateCallback;
      when(mockDataChannel.onDataChannelState = any).thenAnswer((inv) {
        stateCallback = inv.positionalArguments.first
            as Function(RTCDataChannelState)?;
      });

      await svc.connect(mode: 'text');
      stateCallback?.call(RTCDataChannelState.RTCDataChannelOpen);
      stateCallback?.call(RTCDataChannelState.RTCDataChannelOpen);

      expect(count, 1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // sendModeSwitch()
  // ══════════════════════════════════════════════════════════════════════════

  group('WebRTCService sendModeSwitch', () {
    test('sends JSON mode-switch message on open channel', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelOpen);
      when(mockDataChannel.send(any)).thenAnswer((_) async {});

      await svc.connect(mode: 'voice');
      svc.sendModeSwitch('text');

      verify(
        mockDataChannel.send(argThat(predicate<RTCDataChannelMessage>((msg) {
          final data = jsonDecode(msg.text) as Map;
          return data['type'] == 'mode-switch' && data['mode'] == 'text';
        }))),
      ).called(1);
    });

    test('is silent when data channel is not open', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelConnecting);

      await svc.connect(mode: 'voice');
      // Should not throw
      svc.sendModeSwitch('text');

      verifyNever(mockDataChannel.send(any));
    });

    test('is silent when data channel is null (no connect)', () async {
      final svc = _buildService();
      // No connect() call — should not throw
      expect(() => svc.sendModeSwitch('text'), returnsNormally);
      // No resources to clean up (never connected).
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // enableVoiceMode()
  // ══════════════════════════════════════════════════════════════════════════

  group('WebRTCService enableVoiceMode', () {
    test('no-op when not connected', () async {
      final svc = _buildService();
      // No connect() call — should return immediately without throwing
      await svc.enableVoiceMode();
      verifyNever(mockWebRTCWrapper.getUserMedia(any));
      // No resources to clean up (never connected).
    });

    test('fast-path: unmutes track and sends mode-switch when track exists',
        () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      // Must be set up BEFORE connect() so the setter assignment is captured
      Function(RTCPeerConnectionState)? connStateCb;
      when(mockPeerConnection.onConnectionState = any).thenAnswer((inv) {
        connStateCb = inv.positionalArguments.first
            as Function(RTCPeerConnectionState)?;
      });

      when(mockAudioTrack.enabled = any).thenReturn(null);
      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelOpen);
      when(mockDataChannel.send(any)).thenAnswer((_) async {});

      await svc.connect(mode: 'voice'); // creates _audioTrack

      // Simulate peer connection becoming connected → sets _isConnected=true
      connStateCb
          ?.call(RTCPeerConnectionState.RTCPeerConnectionStateConnected);

      clearInteractions(mockWebRTCWrapper); // reset getUserMedia counter

      await svc.enableVoiceMode(); // track already exists → fast path

      // Mic must be unmuted
      verify(mockAudioTrack.enabled = true).called(greaterThanOrEqualTo(1));
      // mode-switch 'voice' must be sent
      verify(
        mockDataChannel.send(argThat(predicate<RTCDataChannelMessage>((msg) {
          final data = jsonDecode(msg.text) as Map;
          return data['type'] == 'mode-switch' && data['mode'] == 'voice';
        }))),
      ).called(1);
      // getUserMedia must NOT be called again
      verifyNever(mockWebRTCWrapper.getUserMedia(any));
    });

    test('fresh-path: creates audio stream when no existing track', () async {
      // Connect in text mode so no audio track is created
      final svc = _buildService();
      addTearDown(svc.disconnect);

      // Must be set up BEFORE connect() so the setter assignment is captured
      Function(RTCPeerConnectionState)? connStateCb;
      when(mockPeerConnection.onConnectionState = any).thenAnswer((inv) {
        connStateCb = inv.positionalArguments.first
            as Function(RTCPeerConnectionState)?;
      });

      when(mockPeerConnection.getSenders())
          .thenAnswer((_) async => <RTCRtpSender>[]);

      // Safety-net in _createPeerConnection checks dataChannel.state
      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelConnecting);

      await svc.connect(mode: 'text');

      // Simulate peer connection becoming connected → sets _isConnected=true
      connStateCb
          ?.call(RTCPeerConnectionState.RTCPeerConnectionStateConnected);

      when(mockPeerConnection.createOffer(any))
          .thenAnswer((_) async => RTCSessionDescription('offer2', 'offer'));

      clearInteractions(mockWebRTCWrapper);
      await svc.enableVoiceMode();

      // A new audio stream must be acquired
      verify(mockWebRTCWrapper.getUserMedia(any)).called(1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // runtime-state DataChannel messages
  // ══════════════════════════════════════════════════════════════════════════

  group('WebRTCService onRuntimeState', () {
    test('fires onRuntimeState with parsed state for runtime-state message',
        () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      Function(RTCDataChannelMessage)? msgHandler;
      when(mockDataChannel.onMessage = any).thenAnswer((inv) {
        msgHandler = inv.positionalArguments[0] as Function(RTCDataChannelMessage)?;
      });

      AgentRuntimeState? received;
      svc.onRuntimeState = (state) => received = state;

      await svc.connect(mode: 'voice');

      expect(msgHandler, isNotNull);
      msgHandler!(RTCDataChannelMessage(
        '{"type":"runtime-state","runtimeState":"thinking"}',
      ));

      expect(received, AgentRuntimeState.thinking);
    });

    test('does not fire onRuntimeState for unknown runtimeState values',
        () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      Function(RTCDataChannelMessage)? msgHandler;
      when(mockDataChannel.onMessage = any).thenAnswer((inv) {
        msgHandler = inv.positionalArguments[0] as Function(RTCDataChannelMessage)?;
      });

      bool callbackFired = false;
      svc.onRuntimeState = (_) => callbackFired = true;

      await svc.connect(mode: 'voice');

      msgHandler!(RTCDataChannelMessage(
        '{"type":"runtime-state","runtimeState":"not_a_real_state"}',
      ));

      expect(callbackFired, isFalse);
    });

    test('does not fire onRuntimeState for chat messages', () async {
      final svc = _buildService();
      addTearDown(svc.disconnect);

      Function(RTCDataChannelMessage)? msgHandler;
      when(mockDataChannel.onMessage = any).thenAnswer((inv) {
        msgHandler = inv.positionalArguments[0] as Function(RTCDataChannelMessage)?;
      });

      bool runtimeCalled = false;
      svc.onRuntimeState = (_) => runtimeCalled = true;

      String? chatText;
      svc.onChatMessage = (text, isUser, isChunk) => chatText = text;

      await svc.connect(mode: 'voice');

      msgHandler!(RTCDataChannelMessage(
        '{"type":"chat","text":"hello","isUser":false,"isChunk":false}',
      ));

      expect(runtimeCalled, isFalse);
      expect(chatText, 'hello');
    });
  });
}
