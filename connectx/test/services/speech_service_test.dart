import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
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
      webRTCServiceFactory: () => mockWebRTCService,
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
}
