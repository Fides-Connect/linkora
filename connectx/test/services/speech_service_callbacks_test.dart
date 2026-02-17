import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:connectx/services/speech_service.dart';
import '../helpers/test_helpers.mocks.dart';

void main() {
  late SpeechService speechService;
  late MockPermissionWrapper mockPermissionWrapper;
  late MockWebRTCService mockWebRTCService;
  late MockRTCVideoRenderer mockRenderer;

  setUp(() {
    mockPermissionWrapper = MockPermissionWrapper();
    mockWebRTCService = MockWebRTCService();
    mockRenderer = MockRTCVideoRenderer();

    // Setup callback setters
    when(mockWebRTCService.onChatMessage = any).thenReturn(null);

    speechService = SpeechService(
      permissionWrapper: mockPermissionWrapper,
      webRTCServiceFactory: (String languageCode) => mockWebRTCService,
    );
  });

  group('SpeechService Callbacks', () {
    test('onSpeechStart callback is triggered when startSpeech is called', () async {
      // Arrange
      bool callbackTriggered = false;
      speechService.onSpeechStart = () {
        callbackTriggered = true;
      };

      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});

      // Act
      await speechService.startSpeech();

      // Assert
      expect(callbackTriggered, true);
    });

    test('onConnected callback is triggered when WebRTC connects', () async {
      // Arrange
      bool connectedCallbackTriggered = false;
      speechService.onConnected = () {
        connectedCallbackTriggered = true;
      };

      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {
        // Simulate WebRTC calling the onConnected callback
        mockWebRTCService.onConnected?.call();
      });

      // Capture the onConnected callback that SpeechService sets on WebRTCService
      when(mockWebRTCService.onConnected = any).thenAnswer((invocation) {
        final callback = invocation.positionalArguments[0] as Function();
        // Store it so we can call it
        when(mockWebRTCService.onConnected).thenReturn(callback);
      });

      // Act
      await speechService.startSpeech();
      
      // Manually trigger the WebRTC onConnected callback
      mockWebRTCService.onConnected?.call();

      // Assert
      expect(connectedCallbackTriggered, true);
    });

    test('onSpeechEnd callback is triggered when stopSpeech is called', () async {
      // Arrange
      bool endCallbackTriggered = false;
      speechService.onSpeechEnd = () {
        endCallbackTriggered = true;
      };

      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});
      
      // Capture the onDisconnected callback
      Function? onDisconnectedCallback;
      when(mockWebRTCService.onDisconnected = any).thenAnswer((invocation) {
        onDisconnectedCallback = invocation.positionalArguments[0] as Function();
      });
      
      // Make disconnect() trigger the onDisconnected callback
      when(mockWebRTCService.disconnect()).thenAnswer((_) async {
        onDisconnectedCallback?.call();
      });

      await speechService.startSpeech();

      // Act
      speechService.stopSpeech();

      // Assert - wait for async operations
      await Future.delayed(Duration(milliseconds: 10));
      expect(endCallbackTriggered, true);
    });

    test('onDisconnected callback is triggered when WebRTC disconnects', () async {
      // Arrange
      bool disconnectedCallbackTriggered = false;
      speechService.onDisconnected = () {
        disconnectedCallbackTriggered = true;
      };

      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});

      // Capture the onDisconnected callback
      when(mockWebRTCService.onDisconnected = any).thenAnswer((invocation) {
        final callback = invocation.positionalArguments[0] as Function();
        when(mockWebRTCService.onDisconnected).thenReturn(callback);
      });

      await speechService.startSpeech();

      // Act - Simulate WebRTC calling onDisconnected
      mockWebRTCService.onDisconnected?.call();

      // Assert
      expect(disconnectedCallbackTriggered, true);
    });
  });

  group('SpeechService Remote Stream Handling', () {
    test('onRemoteStream callback is set up correctly', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect()).thenAnswer((_) async {});

      // Act
      await speechService.startSpeech();

      // Assert - verify the onRemoteStream callback was set
      // We don't test the actual stream handling as it requires Flutter binding
      // initialization which is an implementation detail
      verify(mockWebRTCService.onRemoteStream = any).called(1);
    });
  });

  group('SpeechService Error Handling', () {
    test('handles error when WebRTC connection fails', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(mockWebRTCService.connect())
          .thenThrow(Exception('Connection failed'));

      // Act & Assert
      expect(() => speechService.startSpeech(), throwsException);
    });

    test('handles permission permanently denied', () async {
      // Arrange
      when(mockPermissionWrapper.requestMicrophone())
          .thenAnswer((_) async => PermissionStatus.permanentlyDenied);

      // Act & Assert
      expect(() => speechService.startSpeech(), throwsException);
      verifyNever(mockWebRTCService.connect());
    });
  });
}
