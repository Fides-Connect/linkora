import 'dart:async';
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

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function()? onConnected;
  Function()? onDisconnected;

  SpeechService();

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

    // Initialize WebRTC service
    if (_webrtcService == null) {
      _initializeWebRTC();
    }
  }

  void _initializeWebRTC() {
    print('SpeechService: Initializing WebRTC service');
    
    _webrtcService = WebRTCService();
    
    // Set up WebRTC callbacks
    _webrtcService!.onConnected = () async {
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
      print('SpeechService: Creating new RTCVideoRenderer');
      _remoteRenderer = RTCVideoRenderer();
      await _remoteRenderer!.initialize();
      print('SpeechService: Renderer initialized');
      
      // Set the remote stream to the renderer
      _remoteRenderer!.srcObject = stream;
      print('SpeechService: Remote stream assigned to renderer');
      
      // Ensure the audio track is enabled and not muted
      audioTrack.enabled = true;
      
    } catch (e) {
      print('SpeechService: Error handling remote stream: $e');
      print('SpeechService: Stack trace: ${StackTrace.current}');
    }
  }
}