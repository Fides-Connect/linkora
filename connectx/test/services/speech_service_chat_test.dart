import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:connectx/services/speech_service.dart';
import '../helpers/test_helpers.mocks.dart';

void main() {
  late SpeechService speechService;
  late MockPermissionWrapper mockPermissionWrapper;
  late MockWebRTCService mockWebRTCService;

  setUp(() {
    mockPermissionWrapper = MockPermissionWrapper();
    mockWebRTCService = MockWebRTCService();

    // Wire all required callback setters
    when(mockWebRTCService.onChatMessage = any).thenReturn(null);
    when(mockWebRTCService.onConnected = any).thenReturn(null);
    when(mockWebRTCService.onDisconnected = any).thenReturn(null);
    when(mockWebRTCService.onRemoteStream = any).thenReturn(null);
    when(mockWebRTCService.onError = any).thenReturn(null);
    when(mockWebRTCService.onDataChannelOpen = any).thenReturn(null);

    speechService = SpeechService(
      permissionWrapper: mockPermissionWrapper,
      webRTCServiceFactory: (String languageCode) => mockWebRTCService,
    );
  });

  // ══════════════════════════════════════════════════════════════════════════
  // startSpeech() — mode parameter
  // ══════════════════════════════════════════════════════════════════════════

  group('SpeechService startSpeech mode', () {
    test('voice mode requests microphone permission', () async {
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      await speechService.startSpeech(mode: 'voice');

      verify(mockPermissionWrapper.requestMicrophone()).called(1);
    });

    test('voice mode throws when microphone permission denied', () async {
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.denied);

      expect(() => speechService.startSpeech(mode: 'voice'), throwsException);
      verify(mockPermissionWrapper.requestMicrophone()).called(1);
      verifyNever(mockWebRTCService.connect(mode: anyNamed('mode')));
    });

    test('text mode skips microphone permission check', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      await speechService.startSpeech(mode: 'text');

      verifyNever(mockPermissionWrapper.requestMicrophone());
      verify(mockWebRTCService.connect(mode: 'text')).called(1);
    });

    test('voice mode passes mode=voice to connect()', () async {
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      await speechService.startSpeech(mode: 'voice');

      verify(mockWebRTCService.connect(mode: 'voice')).called(1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // onDataChannelOpen callback forwarding
  // ══════════════════════════════════════════════════════════════════════════

  group('SpeechService onDataChannelOpen', () {
    test('is wired from WebRTC service after startSpeech', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      bool fired = false;
      speechService.onDataChannelOpen = () => fired = true;

      await speechService.startSpeech(mode: 'text');

      // Capture the callback that was passed to webrtcService.onDataChannelOpen
      final verification =
          verify(mockWebRTCService.onDataChannelOpen = captureAny);
      final captured = verification.captured.last as Function()?;
      captured?.call();

      expect(fired, isTrue);
    });

    test('null assignment when service not initialised does not throw', () {
      // Just check nothing blows up
      expect(() => speechService.onDataChannelOpen = null, returnsNormally);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // notifyModeSwitch()
  // ══════════════════════════════════════════════════════════════════════════

  group('SpeechService notifyModeSwitch', () {
    test('delegates to webrtcService.sendModeSwitch after startSpeech', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      await speechService.startSpeech(mode: 'text');
      speechService.notifyModeSwitch('text');

      verify(mockWebRTCService.sendModeSwitch('text')).called(1);
    });

    test('no-op and no throw when service not initialised', () {
      // _webrtcService is null — should not throw
      expect(() => speechService.notifyModeSwitch('text'), returnsNormally);
    });

    test('passes mode argument unchanged', () async {
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});

      await speechService.startSpeech(mode: 'voice');

      speechService.notifyModeSwitch('voice');
      verify(mockWebRTCService.sendModeSwitch('voice')).called(1);

      speechService.notifyModeSwitch('text');
      verify(mockWebRTCService.sendModeSwitch('text')).called(1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // enableVoiceMode()
  // ══════════════════════════════════════════════════════════════════════════

  group('SpeechService enableVoiceMode', () {
    test('no-op when service not initialised', () async {
      // No startSpeech() call
      await expectLater(speechService.enableVoiceMode(), completes);
      verifyNever(mockPermissionWrapper.requestMicrophone());
    });

    test('requests microphone permission before enabling', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockWebRTCService.enableVoiceMode()).thenAnswer((_) async {});
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);

      await speechService.startSpeech(mode: 'text');
      await speechService.enableVoiceMode();

      verify(mockPermissionWrapper.requestMicrophone()).called(1);
    });

    test('throws when microphone permission denied', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.denied);

      await speechService.startSpeech(mode: 'text');

      expect(() => speechService.enableVoiceMode(), throwsException);
    });

    test('delegates to webrtcService.enableVoiceMode after permission', () async {
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockWebRTCService.enableVoiceMode()).thenAnswer((_) async {});
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);

      await speechService.startSpeech(mode: 'text');
      await speechService.enableVoiceMode();

      verify(mockWebRTCService.enableVoiceMode()).called(1);
    });
  });
}
