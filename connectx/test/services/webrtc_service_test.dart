import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:connectx/services/webrtc_service.dart';
import 'package:connectx/services/audio_routing_service.dart';
import '../helpers/test_helpers.mocks.dart';
import '../helpers/test_constants.dart';
import '../mocks/mock_audio_hardware_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late WebRTCService webRTCService;
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

  setUp(() async {
    streamController = StreamController<dynamic>();
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

    // Setup WebSocket mock
    when(mockWebSocketChannel.sink).thenReturn(mockWebSocketSink);
    when(mockWebSocketChannel.stream).thenAnswer((_) => streamController.stream);
    when(mockWebSocketSink.close()).thenAnswer((_) async {
      if (!streamController.isClosed) {
        await streamController.close();
      }
    });

    // Setup User mock
    when(mockFirebaseAuthWrapper.currentUser).thenReturn(mockUser);
    when(mockUser.uid).thenReturn('test_user_id');

    // Setup WebRTC mocks
    when(mockWebRTCWrapper.getUserMedia(any))
        .thenAnswer((_) async => mockLocalStream);
    when(mockLocalStream.getAudioTracks()).thenReturn([mockAudioTrack]);
    when(mockAudioTrack.id).thenReturn('audio_track_id');
    when(mockWebRTCWrapper.createPeerConnection(any, any))
        .thenAnswer((_) async => mockPeerConnection);
    when(mockWebRTCWrapper.createPeerConnection(any))
        .thenAnswer((_) async => mockPeerConnection);
    
    // Setup PeerConnection mocks
    when(mockPeerConnection.addTrack(any, any))
        .thenAnswer((_) async => MockRTCRtpSender());
    when(mockPeerConnection.createOffer(any))
        .thenAnswer((_) async => RTCSessionDescription('offer_sdp', 'offer'));
    when(mockPeerConnection.setLocalDescription(any))
        .thenAnswer((_) async {});
    when(mockPeerConnection.close()).thenAnswer((_) async {});
    when(mockPeerConnection.createDataChannel(any, any))
        .thenAnswer((_) async => mockDataChannel);
    
    // Setup DataChannel mocks - callback setters must return null
    when(mockDataChannel.onMessage = any).thenReturn(null);
    
    // Setup PeerConnection callback setters
    when(mockPeerConnection.onIceCandidate = any).thenReturn(null);
    when(mockPeerConnection.onConnectionState = any).thenReturn(null);
    when(mockPeerConnection.onTrack = any).thenReturn(null);
    
    // Setup LocalStream mocks
    when(mockLocalStream.getTracks()).thenReturn([mockAudioTrack]);
    when(mockLocalStream.dispose()).thenAnswer((_) async {});
    when(mockAudioTrack.stop()).thenAnswer((_) async {});

    when(mockPeerConnection.setRemoteDescription(any))
        .thenAnswer((_) async {});
    when(mockPeerConnection.addCandidate(any))
        .thenAnswer((_) async => true);

    webRTCService = WebRTCService(
      webRTCWrapper: mockWebRTCWrapper,
      webSocketFactory: (uri) => mockWebSocketChannel,
      audioRoutingServiceFactory: () => AudioRoutingService(
        hardwareController: mockAudioHardwareController,
        // Use short intervals for unit tests to avoid leaking timers
        deviceCheckInterval: testDeviceCheckInterval,
        inputChangeDebounce: testInputChangeDebounce,
      ),
      firebaseAuthWrapper: mockFirebaseAuthWrapper,
      serverUrl: 'localhost:8000',
    );
  });

  tearDown(() async {
    // Clean up resources to prevent timer leaks across tests
    // The disconnect() call will trigger streamController.close() via the mock
    await webRTCService.disconnect();
  });

  group('WebRTCService', () {
    test('connect initializes everything correctly', () async {
      // Act
      await webRTCService.connect();

      // Assert
      // 1. Check local stream creation
      verify(mockWebRTCWrapper.getUserMedia(argThat(containsPair('audio', isNotNull)))).called(1);

      // 2. Check signaling connection
      // We can't easily verify the URI passed to factory, but we know the factory was called
      // because we injected the mock channel.

      // 3. Check peer connection creation
      verify(mockWebRTCWrapper.createPeerConnection(any)).called(1);

      // 4. Check adding track
      verify(mockPeerConnection.addTrack(mockAudioTrack, mockLocalStream)).called(1);

      // 5. Check offer creation and setting local description
      verify(mockPeerConnection.createOffer(any)).called(1);
      verify(mockPeerConnection.setLocalDescription(any)).called(1);
      
      // 6. Check sending offer via signaling
      verify(mockWebSocketSink.add(argThat(predicate((String msg) {
        final Map<String, dynamic> data = jsonDecode(msg);
        return data['type'] == 'offer' && data['sdp'] == 'offer_sdp';
      })))).called(1);
    });

    test('disconnect cleans up resources', () async {
      // Arrange
      await webRTCService.connect();

      // Act
      await webRTCService.disconnect();

      // Assert
      verify(mockWebSocketSink.close()).called(1);
      verify(mockLocalStream.dispose()).called(1);
      verify(mockPeerConnection.close()).called(1);
    });
    test('handles incoming answer message', () async {
      // Arrange
      await webRTCService.connect();
      
      // Act
      final answerMap = {
        'type': 'answer',
        'sdp': 'answer_sdp',
      };
      streamController.add(jsonEncode(answerMap));
      
      // Wait for microtasks to complete
      await Future.delayed(Duration.zero);

      // Assert
      verify(mockPeerConnection.setRemoteDescription(argThat(predicate((RTCSessionDescription desc) {
        return desc.type == 'answer' && desc.sdp == 'answer_sdp';
      })))).called(1);
    });

    test('handles incoming candidate message', () async {
      // Arrange
      await webRTCService.connect();
      
      // Simulate remote description set so candidate is added immediately
      // We need to send answer first or manually set the flag if possible.
      // Since _remoteDescriptionSet is private, we should send an answer first.
      
      final answerMap = {
        'type': 'answer',
        'sdp': 'answer_sdp',
      };
      streamController.add(jsonEncode(answerMap));
      await Future.delayed(Duration.zero);

      // Act
      final candidateMap = {
        'type': 'ice-candidate',
        'candidate': {
          'candidate': 'candidate_string',
          'sdpMid': 'audio',
          'sdpMLineIndex': 0,
        }
      };
      streamController.add(jsonEncode(candidateMap));
      
      // Wait for microtasks to complete
      await Future.delayed(Duration.zero);

      // Assert
      verify(mockPeerConnection.addCandidate(argThat(predicate((RTCIceCandidate cand) {
        return cand.candidate == 'candidate_string' && 
               cand.sdpMid == 'audio' && 
               cand.sdpMLineIndex == 0;
      })))).called(1);
    });

    test('microphone muted state starts as true', () async {
      // Assert - Test the initial state without connecting
      expect(webRTCService.isMicrophoneMuted, true);
    }, timeout: Timeout(Duration(seconds: 5)));

    test('setMicrophoneMuted updates audio track enabled state', () async {
      // Arrange
      when(mockAudioTrack.enabled).thenReturn(false); // Initially muted
      when(mockAudioTrack.enabled = any).thenReturn(null);
      await webRTCService.connect();
      
      // Verify initial setup (track is created with startMuted: true)
      verify(mockAudioTrack.enabled = false).called(1);
      clearInteractions(mockAudioTrack); // Clear for actual test
      
      // Initially should be muted
      expect(webRTCService.isMicrophoneMuted, true);
      
      // Act - unmute
      webRTCService.setMicrophoneMuted(false);
      
      // Assert
      verify(mockAudioTrack.enabled = true).called(1);
      
      // Act - mute again
      webRTCService.setMicrophoneMuted(true);
      
      // Assert
      verify(mockAudioTrack.enabled = false).called(1);
    });

    test('audioRouting is accessible after connection', () async {
      // Act
      await webRTCService.connect();
      
      // Assert - audioRouting should be initialized (on non-web)
      expect(webRTCService.audioRouting, isNotNull);
    });
  });

  group('WebRTCService sendTextMessage', () {
    test('calls onError when data channel is null (no prior connect)', () {
      // Arrange
      String? capturedError;
      webRTCService.onError = (e) => capturedError = e;

      // Act — _dataChannel is null since connect() was never called
      webRTCService.sendTextMessage('hello');

      // Assert
      expect(capturedError, isNotNull);
      expect(capturedError, contains('Cannot send message'));
      verifyNever(mockDataChannel.send(any));
    });

    test('calls onError when data channel is not open', () async {
      // Arrange
      await webRTCService.connect();
      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelConnecting);

      String? capturedError;
      webRTCService.onError = (e) => capturedError = e;

      // Act
      webRTCService.sendTextMessage('hello');

      // Assert
      expect(capturedError, isNotNull);
      expect(capturedError, contains('Cannot send message'));
      verifyNever(mockDataChannel.send(any));
    });

    test('sends JSON-encoded message over open data channel', () async {
      // Arrange
      await webRTCService.connect();
      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelOpen);
      when(mockDataChannel.send(any)).thenAnswer((_) async {});

      bool errorCalled = false;
      webRTCService.onError = (_) => errorCalled = true;

      // Act
      webRTCService.sendTextMessage('hello');

      // Assert
      expect(errorCalled, false);
      verify(mockDataChannel.send(argThat(predicate<RTCDataChannelMessage>((msg) {
        final data = jsonDecode(msg.text);
        return data['type'] == 'text-input' && data['text'] == 'hello';
      })))).called(1);
    });

    test('calls onError when data channel send throws an exception', () async {
      // Arrange
      await webRTCService.connect();
      when(mockDataChannel.state)
          .thenReturn(RTCDataChannelState.RTCDataChannelOpen);
      when(mockDataChannel.send(any)).thenThrow(Exception('network error'));

      String? capturedError;
      webRTCService.onError = (e) => capturedError = e;

      // Act
      webRTCService.sendTextMessage('hello');

      // Assert
      expect(capturedError, isNotNull);
      expect(capturedError, contains('Failed to send'));
    });
  });

  group('WebRTCService URL scheme detection', () {
    test('bare host:port produces ws:// URL and no token request', () async {
      // webRTCService is already built with serverUrl: 'localhost:8000' (bare)
      await webRTCService.connect();
      // getIdToken must NOT be called for plain ws connections
      verifyNever(mockFirebaseAuthWrapper.getIdToken());
    });

    test('https:// URL produces wss connection and attaches Firebase ID token', () async {
      // Arrange – build a service with a Cloud Run HTTPS URL
      final secureService = WebRTCService(
        webRTCWrapper: mockWebRTCWrapper,
        webSocketFactory: (uri) {
          // Verify wss scheme and token query param
          expect(uri.scheme, 'wss');
          expect(uri.queryParameters['token'], 'fake-id-token');
          return mockWebSocketChannel;
        },
        audioRoutingServiceFactory: () => AudioRoutingService(
          hardwareController: mockAudioHardwareController,
          deviceCheckInterval: testDeviceCheckInterval,
          inputChangeDebounce: testInputChangeDebounce,
        ),
        firebaseAuthWrapper: mockFirebaseAuthWrapper,
        serverUrl: 'https://ai-assistant-test.run.app',
      );
      when(mockFirebaseAuthWrapper.getIdToken())
          .thenAnswer((_) async => 'fake-id-token');

      // Act
      await secureService.connect();

      // Assert token was fetched
      verify(mockFirebaseAuthWrapper.getIdToken()).called(1);

      await secureService.disconnect();
    });

    test('http:// URL produces ws connection and no token request', () async {
      // Arrange
      final httpService = WebRTCService(
        webRTCWrapper: mockWebRTCWrapper,
        webSocketFactory: (uri) {
          expect(uri.scheme, 'ws');
          return mockWebSocketChannel;
        },
        audioRoutingServiceFactory: () => AudioRoutingService(
          hardwareController: mockAudioHardwareController,
          deviceCheckInterval: testDeviceCheckInterval,
          inputChangeDebounce: testInputChangeDebounce,
        ),
        firebaseAuthWrapper: mockFirebaseAuthWrapper,
        serverUrl: 'http://192.168.1.100:8080',
      );

      await httpService.connect();

      verifyNever(mockFirebaseAuthWrapper.getIdToken());

      await httpService.disconnect();
    });
  });
}
