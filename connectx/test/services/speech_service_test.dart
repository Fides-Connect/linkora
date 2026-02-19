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

    // Setup callback setters
    when(mockWebRTCService.onChatMessage = any).thenReturn(null);

    speechService = SpeechService(
      permissionWrapper: mockPermissionWrapper,
      webRTCServiceFactory: (String languageCode) => mockWebRTCService,
    );
  });

  group('SpeechService', () {
    test('startSpeech connects to WebRTC service when permission granted', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});

      // Act
      await speechService.startSpeech();

      // Assert
      verify(mockPermissionWrapper.requestMicrophone()).called(1);
      verify(mockWebRTCService.connect()).called(1);
    });

    test('startSpeech throws exception when permission denied', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.denied);

      // Act & Assert
      expect(() => speechService.startSpeech(), throwsException);
      verify(mockPermissionWrapper.requestMicrophone()).called(1);
      verifyNever(mockWebRTCService.connect());
    });

    test('stopSpeech disconnects WebRTC service', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});
      await speechService.startSpeech();

      // Act
      speechService.stopSpeech();

      // Assert
      verify(mockWebRTCService.disconnect()).called(1);
    });
  });

  group('SpeechService sendTextMessage', () {
    test('returns false when WebRTC service is not initialized', () {
      // Act — no startSpeech() call, so _webrtcService is null
      final result = speechService.sendTextMessage('hello');

      // Assert
      expect(result, false);
      verifyNever(mockWebRTCService.sendTextMessage(any));
    });

    test('returns true and forwards text to WebRTC service', () async {
      // Arrange — text mode skips microphone permission
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      await speechService.startSpeech(mode: 'text');

      // Act
      final result = speechService.sendTextMessage('hello world');

      // Assert
      expect(result, true);
      verify(mockWebRTCService.sendTextMessage('hello world')).called(1);
    });

    test('forwards exact text content to WebRTC service', () async {
      // Arrange
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      await speechService.startSpeech(mode: 'text');

      const message = 'Specific test message 123';

      // Act
      speechService.sendTextMessage(message);

      // Assert
      verify(mockWebRTCService.sendTextMessage(message)).called(1);
    });

    test('returns false after stopSpeech clears the WebRTC service', () async {
      // Arrange
      when(mockWebRTCService.connect(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      await speechService.startSpeech(mode: 'text');
      speechService.stopSpeech();

      // Act
      final result = speechService.sendTextMessage('hello');

      // Assert
      expect(result, false);
    });
  });
}
