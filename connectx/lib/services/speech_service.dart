import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'webrtc_service.dart';

/// Speech service that uses WebRTC to communicate with the AI-Assistant server
/// The server handles Speech-to-Text, LLM processing, and Text-to-Speech
class SpeechService {
  // WebRTC service for server communication
  WebRTCService? _webrtcService;
  final bool _ownsWebRTC;
  
  // Remote audio renderer for WebRTC audio playback
  RTCVideoRenderer? _remoteRenderer;

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function()? onConnected;
  Function()? onDisconnected;

  /// Create a SpeechService with an optional existing WebRTC service.
  /// If [webrtcService] is provided, it will reuse the existing connection.
  /// Otherwise, it creates a new WebRTC service when needed.
  SpeechService({WebRTCService? webrtcService})
      : _webrtcService = webrtcService,
        _ownsWebRTC = webrtcService == null;

  void stopSpeech() async {
    debugPrint('SpeechService: Stopping speech session');
    
    // Always disconnect to stop audio streaming
    if (_webrtcService != null) {
      await _webrtcService!.disconnect();
      // Only nullify if we own the service (for re-creation next time)
      if (_ownsWebRTC) {
        _webrtcService = null;
      }
    }

    // Stop and clean up audio renderer
    if (_remoteRenderer != null) {
      _remoteRenderer!.srcObject = null;
      await _remoteRenderer!.dispose();
      _remoteRenderer = null;
    }
    
    debugPrint('SpeechService: Speech session stopped');
  }

  /// Start speech session by connecting to AI-Assistant server via WebRTC
  /// The server will handle audio streaming, STT, LLM, and TTS processing
  Future<void> startSpeech() async {
    onSpeechStart?.call();
    
    try {
      // Initialize audio player and WebRTC
      await _initialize();
      
      // Always establish fresh WebRTC connection for each session
      // This ensures proper audio processor setup on server side
      if (_webrtcService != null) {
        // Disconnect first if already connected (to start fresh)
        if (_webrtcService!.isConnected) {
          debugPrint('SpeechService: Disconnecting existing connection to start fresh');
          await _webrtcService!.disconnect();
        }
        
        debugPrint('SpeechService: Connecting to AI-Assistant server');
        await _webrtcService!.connect();
      } else {
        throw Exception('WebRTC service not initialized');
      }
      
      debugPrint('SpeechService: Ready for speech interaction');
      
    } catch (e) {
      debugPrint('SpeechService: Error in startSpeech: $e');
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
    } else if (!_ownsWebRTC) {
      // If we're using a shared service, just set up our callbacks
      _setupWebRTCCallbacks();
    }
  }

  void _initializeWebRTC() {
    debugPrint('SpeechService: Initializing new WebRTC service');
    
    _webrtcService = WebRTCService();
    _setupWebRTCCallbacks();
  }

  void _setupWebRTCCallbacks() {
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
    
    _webrtcService!.onRemoteStream = (MediaStream stream) {
      debugPrint('SpeechService: Received remote audio stream');
      Future.microtask(() => _handleRemoteStream(stream));
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
      debugPrint('SpeechService: Got remote audio track: ${audioTrack.id}, enabled: ${audioTrack.enabled}, muted: ${audioTrack.muted}');
      
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
}