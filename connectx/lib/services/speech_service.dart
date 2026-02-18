import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'webrtc_service.dart';
import 'wrappers.dart';
import '../models/app_types.dart';

/// Speech service that uses WebRTC to communicate with the AI-Assistant server
/// The server handles Speech-to-Text, LLM processing, and Text-to-Speech
class SpeechService {
  // WebRTC service for server communication
  WebRTCService? _webrtcService;

  // Remote audio renderer for WebRTC audio playback
  RTCVideoRenderer? _remoteRenderer;

  // Dependencies
  final PermissionWrapper _permissionWrapper;
  final WebRTCService Function(String) _webRTCServiceFactory;

  // Language configuration
  String _languageCode = 'de';

  // Callbacks
  OnSpeechStartCallback? onSpeechStart;
  OnSpeechEndCallback? onSpeechEnd;
  OnConnectedCallback? onConnected;
  OnDisconnectedCallback? onDisconnected;
  OnChatMessageCallback? onChatMessage;
  Function()? onDataChannelOpen;

  SpeechService({
    PermissionWrapper? permissionWrapper,
    WebRTCService Function(String)? webRTCServiceFactory,
  }) : _permissionWrapper = permissionWrapper ?? PermissionWrapper(),
       _webRTCServiceFactory =
           webRTCServiceFactory ??
           ((lang) => WebRTCService(languageCode: lang));

  /// Set the language code for the AI Assistant
  void setLanguageCode(String languageCode) {
    _languageCode = languageCode;
  }

  /// Check if microphone is currently muted
  bool get isMicrophoneMuted => _webrtcService?.isMicrophoneMuted ?? true;

  void setMicrophoneMuted(bool muted) {
    _webrtcService?.setMicrophoneMuted(muted);
  }

  void stopSpeech() async {
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
  Future<void> startSpeech({String mode = 'voice'}) async {
    onSpeechStart?.call();

    try {
      // Initialize audio player and WebRTC
      await _initialize();

      // Connect to AI-Assistant server
      await _webrtcService!.connect(mode: mode);

      debugPrint('SpeechService: Connected to AI-Assistant server');
    } catch (e) {
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> _initialize() async {
    // Check microphone permission
    final microphoneRequest = await _permissionWrapper.requestMicrophone();
    if (!microphoneRequest.isGranted) {
      throw Exception('Microphone permission denied');
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

    _webrtcService!.onRemoteStream = (MediaStream stream) {
      debugPrint('SpeechService: Received remote audio stream');
      Future.microtask(() => _handleRemoteStream(stream));
    };

    _webrtcService!.onDataChannelOpen = () {
      debugPrint('SpeechService: Data channel open');
      onDataChannelOpen?.call();
    };

    _webrtcService!.onError = (String error) {
      debugPrint('SpeechService: WebRTC error: $error');
      onSpeechEnd?.call();
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
  void sendTextMessage(String text) {
    _webrtcService?.sendTextMessage(text);
  }
}
