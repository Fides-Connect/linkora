import 'dart:async';
import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'webrtc_service.dart';

/// Speech service that uses WebRTC to communicate with the AI-Assistant server
/// The server handles Speech-to-Text, LLM processing, and Text-to-Speech
class SpeechService {
  // WebRTC service for server communication
  WebRTCService? _webrtcService;
  
  // Remote audio renderer for WebRTC audio playback
  RTCVideoRenderer? _remoteRenderer;
  
  // Remote audio stream subscription
  StreamSubscription<dynamic>? _remoteAudioSubscription;

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function()? onConnected;
  Function()? onDisconnected;

  // Android audio-mode channel
  static const MethodChannel _audioModeChannel = MethodChannel(
    'connectx/audio_mode',
  );

  SpeechService();

  void stopSpeech() {
    // Stop and clean up WebRTC service
    _webrtcService?.disconnect();
    _webrtcService = null;

    // Stop and clean up audio renderer
    if (_remoteRenderer != null) {
      _remoteRenderer!.srcObject = null;
      _remoteRenderer!.dispose();
      _remoteRenderer = null;
    }
    
    _remoteAudioSubscription?.cancel();
    _remoteAudioSubscription = null;
  }

  /// Start speech session by connecting to AI-Assistant server via WebRTC
  /// The server will handle audio streaming, STT, LLM, and TTS processing
  Future<void> startSpeech() async {
    onSpeechStart?.call();
    
    try {
      // Initialize audio player and WebRTC
      await _initialize();
      
      // Connect to AI-Assistant server
      await _webrtcService!.connect();
      
      print('SpeechService: Connected to AI-Assistant server');
      
    } catch (e) {
      print('SpeechService: Error in startSpeech: $e');
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> _initialize() async {
    // Check microphone permission
    final microphoneRequest = await Permission.microphone.request();
    if (!microphoneRequest.isGranted) {
      throw Exception('Microphone permission denied');
    }

    // Android-specific audio mode setup (only on mobile platforms)
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      await _setAndroidCommunicationMode();
    }

    // Initialize WebRTC service
    if (_webrtcService == null) {
      _initializeWebRTC();
    }
  }

  Future<void> _setAndroidCommunicationMode() async {
    try {
      final res = await _audioModeChannel.invokeMethod<Map>(
        'forceModeInCommunication',
      );
      print('Android audio mode set: $res');
    } catch (e) {
      print('Failed to set MODE_IN_COMMUNICATION: $e');
    }
  }

  void _initializeWebRTC() {
    print('SpeechService: Initializing WebRTC service');
    
    _webrtcService = WebRTCService();
    
    // Set up WebRTC callbacks
    _webrtcService!.onConnected = () {
      print('SpeechService: WebRTC connected');
      onConnected?.call();
    };
    
    _webrtcService!.onDisconnected = () {
      print('SpeechService: WebRTC disconnected');
      onDisconnected?.call();
      onSpeechEnd?.call();
    };
    
    _webrtcService!.onRemoteStream = (MediaStream stream) {
      print('SpeechService: Received remote audio stream');
      // Make the call async by wrapping in Future
      Future.microtask(() => _handleRemoteStream(stream));
    };
    
    _webrtcService!.onError = (String error) {
      print('SpeechService: WebRTC error: $error');
      onSpeechEnd?.call();
    };
  }

  /// Handle incoming remote audio stream from AI-Assistant server
  /// This stream contains the processed audio (STT -> LLM -> TTS)
  Future<void> _handleRemoteStream(MediaStream stream) async {
    print('SpeechService: Setting up remote audio stream playback');
    
    try {
      // Get the audio track
      final audioTracks = stream.getAudioTracks();
      if (audioTracks.isEmpty) {
        print('SpeechService: No audio tracks in remote stream');
        return;
      }
      
      final audioTrack = audioTracks[0];
      print('SpeechService: Got remote audio track: ${audioTrack.id}, enabled: ${audioTrack.enabled}, muted: ${audioTrack.muted}');
      
      // Clean up any existing renderer
      if (_remoteRenderer != null) {
        print('SpeechService: Disposing existing renderer');
        _remoteRenderer!.srcObject = null;
        await _remoteRenderer!.dispose();
      }
      
      // Create and initialize an RTCVideoRenderer to handle the audio stream
      // flutter_webrtc uses RTCVideoRenderer for both audio and video playback
      print('SpeechService: Creating new RTCVideoRenderer');
      _remoteRenderer = RTCVideoRenderer();
      await _remoteRenderer!.initialize();
      print('SpeechService: Renderer initialized');
      
      // Set the remote stream to the renderer
      _remoteRenderer!.srcObject = stream;
      print('SpeechService: Remote stream assigned to renderer');
      
      // Ensure the audio track is enabled and not muted
      audioTrack.enabled = true;
      
      // Enable speaker output on mobile devices
      await _enableSpeakerOutput();
      
      print('SpeechService: Remote audio stream is now playing through speakers');
      print('SpeechService: Audio track state - enabled: ${audioTrack.enabled}, muted: ${audioTrack.muted}');
      
    } catch (e) {
      print('SpeechService: Error handling remote stream: $e');
      print('SpeechService: Stack trace: ${StackTrace.current}');
    }
  }
  
  /// Enable speaker output for audio playback on mobile devices
  Future<void> _enableSpeakerOutput() async {
    try {
      if (!kIsWeb && (defaultTargetPlatform == TargetPlatform.iOS || 
                     defaultTargetPlatform == TargetPlatform.android)) {
        print('SpeechService: Enabling speaker output for mobile platform');
        await Helper.setSpeakerphoneOn(true);
        print('SpeechService: Speaker output enabled');
      }
    } catch (e) {
      print('SpeechService: Error enabling speaker output: $e');
      // Continue anyway as this is not critical
    }
  }
}